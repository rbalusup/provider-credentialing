# System Architecture

## Overview

The provider credentialing system is a four-stage pipeline that takes a provider's identity as input and produces a structured credentialing report as output. Each stage is independently testable and can fail gracefully without crashing the entire pipeline.

```
                        ┌──────────────────┐
                        │   CLI / Python   │
                        │   API caller     │
                        └────────┬─────────┘
                                 │ Provider(name, NPI, state)
                                 ▼
                    ┌────────────────────────┐
                    │  CredentialingOrchest- │
                    │  rator                 │
                    │  (orchestrator.py)     │
                    └──┬───────┬────────┬───┘
                       │       │        │
              Stage 1  │  Stage 2  Stage 3   Stage 4
                       │       │        │
               ┌───────▼─┐ ┌───▼───┐ ┌─▼──────┐ ┌──────────┐
               │  Web    │ │Claude │ │Sanction│ │Normalize │
               │ Scraper │ │Extrac-│ │Detect- │ │& Validate│
               │         │ │tor    │ │ion     │ │          │
               └───────┬─┘ └───┬───┘ └─┬──────┘ └────┬─────┘
                       │       │        │              │
                       └───────┴────────┴──────────────┘
                                        │
                               ┌────────▼────────┐
                               │ CredentialingTask│
                               │ (result object)  │
                               └─────────────────┘
```

---

## Pipeline Stages

### Stage 1 — Data Fetch (`_extract_from_sources`)

Fetches raw HTML from each configured source in parallel.

- Uses `WebScraper` (async httpx) for plain HTTP sources
- Falls back to `SeleniumScraper` (headless Chrome) for JavaScript-heavy sites like NPDB
- Returns a list of `{source, html_content, url, status}` dicts
- Errors per source are caught and logged; the pipeline continues with remaining sources

**Configured sources:**

| Source | URL pattern | Method |
|--------|-------------|--------|
| CA Medical Board | `search.dca.ca.gov` | HTTP |
| OIG Exclusions | `exclusions.oig.hhs.gov` | HTTP |
| NPDB | `npdb.hrsa.gov` | Selenium |

### Stage 2 — Structured Extraction (`_extract_credentials`)

For each successful fetch, calls `ClaudeExtractor.extract_provider_info(html)`.

Claude reads the raw HTML and returns a JSON object with fields: `first_name`, `last_name`, `license_number`, `license_status`, `issue_date`, `expiration_date`, `confidence`.

Each result becomes a `Credential` Pydantic model and is appended to `task.credentials`.

### Stage 3 — Sanctions Detection (`_check_sanctions`)

Calls `ClaudeExtractor.detect_sanctions(provider_data)` with the provider's known info.

Claude returns: `red_flags[]`, `sanction_risk_score`, `requires_investigation`, `investigation_notes`.

Each red flag becomes a `Sanction` model with `source="AI Analysis"`. In a production system this stage would also query real sanction databases directly.

### Stage 4 — Normalization (`_normalize_data`)

Aggregates everything into a final summary dict stored in `task.normalized_data`:

```json
{
  "provider": { ... },
  "credentials": [ ... ],
  "sanctions": [ ... ],
  "summary": {
    "total_credentials": 2,
    "active_credentials": 1,
    "expired_credentials": 1,
    "sanctions_found": 0,
    "requires_review": true
  },
  "normalized_at": "2026-03-04T12:00:00"
}
```

---

## Component Map

```
credentialing/
├── models.py            Data layer — Pydantic models, enums
├── config.py            Configuration — pydantic-settings, reads .env
├── logging_config.py    Observability — structlog structured logging
├── scraper.py           I/O — async HTTP + Selenium, retry logic
├── spiders.py           I/O — Scrapy spiders for complex crawls
├── claude_extractor.py  AI — Claude API calls (extract, normalize, detect)
└── orchestrator.py      Control — pipeline coordinator, stages 1-4
```

### Data models (`models.py`)

```
Provider           ← input: who to check
  └── CredentialingTask  ← pipeline state
        ├── ExtractionResult[]  ← raw fetched HTML per source
        ├── Credential[]        ← extracted license records
        ├── Sanction[]          ← detected red flags
        └── normalized_data     ← final summary dict
```

**Enums:**

| Enum | Values |
|------|--------|
| `CredentialStatus` | `active`, `inactive`, `expired`, `suspended`, `revoked`, `unknown` |
| `SanctionStatus` | `clear`, `sanctioned`, `under_investigation`, `unknown` |
| `ExtractionStatus` | `pending`, `in_progress`, `success`, `failed`, `partial` |

---

## Resilience Design

### Retries

Both the scraper and Claude extractor use [Tenacity](https://tenacity.readthedocs.io/) decorators:

```
WebScraper.fetch        → retry on httpx.HTTPError, asyncio.TimeoutError
                          stop_after_attempt(3), wait_exponential(1..10s)

ClaudeExtractor.*       → retry on RateLimitError, APIError
                          stop_after_attempt(3), wait_exponential(2..10s)
```

### Error isolation

Each source is wrapped in `try/except` in `_extract_from_sources`. A single source failing does not abort the pipeline — the task collects errors in `task.errors[]` and marks itself `PARTIAL` or `FAILED` only if all sources fail.

### Rate limiting

`WebScraper.fetch_batch` uses an `asyncio.Semaphore` to cap concurrent requests at `settings.concurrent_requests` (default: 4) and inserts a sleep of `1 / requests_per_second` between requests.

### CAPTCHA + bot detection

`WebScraper._detect_captcha` checks the response body for keywords (`recaptcha`, `hcaptcha`, `captcha`, `security check`, `verify you are human`). When detected, the scraper returns `ScraperStatus.CAPTCHA` instead of retrying, so the orchestrator can fall back to Selenium.

---

## Async Design

The scraper and orchestrator are fully async. The only `asyncio.run()` call is at the CLI boundary in `cli.py`. This makes the library embeddable in any async application (FastAPI, etc.) without modification.

```
asyncio.run()         ← CLI entry point only
    └── orchestrator.process_provider()    async
          ├── _extract_from_sources()      async
          │     └── scraper.fetch_batch()  async (concurrent)
          ├── _extract_credentials()       async (calls sync Claude)
          ├── _check_sanctions()           async (calls sync Claude)
          └── _normalize_data()            async
```

`ClaudeExtractor` methods are synchronous (the Anthropic SDK's sync client). They are called inside async methods but do not block the event loop long enough to matter for this workload. For high-throughput use cases, wrap them with `asyncio.to_thread()`.

---

## Observability

All components use `structlog` bound loggers:

```python
logger = get_logger(__name__)
logger.info("event_name", key1=value1, key2=value2)
```

In production (`LOG_FORMAT=json`) this produces machine-parseable JSON:

```json
{
  "event": "fetch_success",
  "url": "https://search.dca.ca.gov/...",
  "status_code": 200,
  "content_length": 14823,
  "timestamp": "2026-03-04T12:00:00Z",
  "level": "info"
}
```

Key events to monitor:

| Event | Level | Meaning |
|-------|-------|---------|
| `starting_credentialing_process` | info | Pipeline started |
| `credentialing_process_complete` | info | Pipeline succeeded |
| `credentialing_process_failed` | error | Pipeline failed |
| `rate_limited` | warning | Source returned 429 |
| `captcha_detected` | warning | CAPTCHA found, Selenium needed |
| `red_flags_detected` | warning | Sanctions found for provider |
| `claude_api_error` | warning | Claude call failed (will retry) |

---

## Extension Points

### Adding a new data source

1. **Spider** (`spiders.py`): subclass `BaseProviderSpider`, implement `start_requests` and `parse`
2. **Orchestrator** (`orchestrator.py`): add entry to `source_configs` dict in `_extract_from_sources`
3. **Tests**: mock `_extract_from_sources` return to include the new source's HTML

### Replacing Claude with a different LLM

`ClaudeExtractor` is only used in `orchestrator.py`. Swap it for any class that implements the same three methods:
- `extract_provider_info(html: str) -> dict`
- `normalize_credential_data(raw: dict, source: str) -> dict`
- `detect_sanctions(provider: dict) -> dict`

### Adding persistence

The `CredentialingTask` model is fully serializable via `task.model_dump_json()`. Drop in SQLAlchemy or any ORM to persist tasks before returning them from `process_provider`.