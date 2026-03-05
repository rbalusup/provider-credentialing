# Python API Reference

All public classes and methods available when using this package as a library.

---

## Models (`credentialing.models`)

### `Provider`

Input model. Identifies the provider to credential.

```python
from credentialing.models import Provider

provider = Provider(
    first_name="John",
    last_name="Doe",
    middle_name="Michael",        # optional
    npi="1234567890",             # optional
    license_number="MD123456",    # optional
    state_code="CA",              # required, 2-char ISO code
    specialty="Internal Medicine",# optional
    provider_type="MD",           # optional
    date_of_birth="1975-05-20",   # optional
    email="john.doe@example.com", # optional
    phone="555-123-4567",         # optional
)
```

| Field | Type | Required |
|-------|------|----------|
| `first_name` | `str` | Yes |
| `last_name` | `str` | Yes |
| `state_code` | `str` (2 chars) | Yes |
| `npi` | `str \| None` | No |
| `license_number` | `str \| None` | No |
| All others | optional | No |

---

### `Credential`

Represents a verified license or certification.

```python
from credentialing.models import Credential, CredentialStatus

credential = Credential(
    provider_id="provider_123",
    credential_type="license",           # "license", "DEA", "board_certification"
    issuing_authority="CA Medical Board",
    credential_number="MD123456",
    issue_date="2020-01-15",             # YYYY-MM-DD
    expiration_date="2026-01-15",        # YYYY-MM-DD
    status=CredentialStatus.ACTIVE,
    source_url="https://search.dca.ca.gov/...",
    verified_at=datetime.now(),
)
```

**`CredentialStatus` enum values:** `active`, `inactive`, `expired`, `suspended`, `revoked`, `unknown`

---

### `Sanction`

Represents a detected sanction or red flag.

```python
from credentialing.models import Sanction, SanctionStatus

sanction = Sanction(
    provider_id="provider_123",
    sanction_type="exclusion",           # "exclusion", "license_suspension", "red_flag"
    description="Excluded from Medicare",
    sanction_date="2023-06-01",
    status=SanctionStatus.SANCTIONED,
    source="OIG",                        # "OIG", "NPDB", "AI Analysis"
    source_url="https://exclusions.oig.hhs.gov/...",
)
```

**`SanctionStatus` enum values:** `clear`, `sanctioned`, `under_investigation`, `unknown`

---

### `CredentialingTask`

The full pipeline state object — input + all results.

```python
task.provider           # Provider
task.sources            # List[str] — sources checked
task.status             # ExtractionStatus
task.extraction_results # List[ExtractionResult] — raw fetched data
task.credentials        # List[Credential]
task.sanctions          # List[Sanction]
task.normalized_data    # Dict — summary + all data normalized
task.errors             # List[str] — error messages per failed stage
task.created_at         # datetime
task.updated_at         # datetime
```

**`ExtractionStatus` enum values:** `pending`, `in_progress`, `success`, `failed`, `partial`

**Serialize to JSON:**
```python
import json
json.loads(task.model_dump_json())
```

---

## ClaudeExtractor (`credentialing.claude_extractor`)

Wraps the Anthropic API for three extraction tasks. All methods include automatic retry (up to 3 attempts with exponential backoff on `RateLimitError` / `APIError`).

### `extract_provider_info(html_content)`

Extracts structured provider fields from raw HTML.

```python
from credentialing.claude_extractor import ClaudeExtractor

extractor = ClaudeExtractor()
result = extractor.extract_provider_info(html_content)
```

**Returns:**
```python
{
    "success": True,
    "data": {
        "first_name": "John",
        "last_name": "Doe",
        "license_number": "MD123456",
        "license_status": "active",       # normalized enum value
        "issue_date": "2020-01-15",       # YYYY-MM-DD
        "expiration_date": "2026-01-15",
        "confidence": {                   # 0.0–1.0 per field
            "first_name": 0.99,
            "license_number": 0.97
        }
    },
    "processing_time_ms": 342,
    "raw_response": "..."
}

# On failure:
{"success": False, "error": "...", "processing_time_ms": 100}
```

---

### `normalize_credential_data(raw_data, source_name)`

Normalizes raw extracted data — standardizes dates, status values, flags quality issues.

```python
result = extractor.normalize_credential_data(
    raw_data={"issue_date": "01/15/2020", "license_status": "VALID"},
    source_name="CA Medical Board"
)
```

**Returns:**
```python
{
    "success": True,
    "data": {
        "normalized_data": { "issue_date": "2020-01-15", "license_status": "active" },
        "data_quality_issues": [],
        "requires_manual_review": False,
        "confidence_score": 0.95
    },
    "processing_time_ms": 280
}
```

---

### `detect_sanctions(provider_data)`

Analyzes provider data for red flags and compliance risks.

```python
result = extractor.detect_sanctions({
    "first_name": "John",
    "last_name": "Doe",
    "license_status": "expired",
    "npi": "1234567890"
})
```

**Returns:**
```python
{
    "success": True,
    "data": {
        "red_flags": ["License expired", "Missing NPI verification"],
        "sanction_risk_score": 0.7,       # 0.0 (clear) – 1.0 (high risk)
        "requires_investigation": True,
        "investigation_notes": "Expired license requires immediate follow-up"
    },
    "processing_time_ms": 310
}
```

---

### `batch_extract_providers(providers_html)`

Process multiple providers sequentially, returning results with their IDs attached.

```python
results = extractor.batch_extract_providers([
    ("provider_1", "<html>...</html>"),
    ("provider_2", "<html>...</html>"),
])
# Each result dict has an added "provider_id" field
```

---

## WebScraper (`credentialing.scraper`)

Async HTTP scraper with retry, rate limiting, CAPTCHA detection, and anti-bot handling.

### Basic usage

```python
import asyncio
from credentialing.scraper import WebScraper, ScraperStatus

async def main():
    async with WebScraper() as scraper:
        result = await scraper.fetch("https://example.com")

        if result.status == ScraperStatus.SUCCESS:
            html = result.html
        elif result.status == ScraperStatus.CAPTCHA:
            # Fall back to Selenium
            pass
        elif result.status == ScraperStatus.RATE_LIMITED:
            # Back off and retry later
            pass

asyncio.run(main())
```

### `fetch(url) -> ScraperResult`

Fetches a single URL with retry logic.

**`ScraperResult` fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | `ScraperStatus` | Outcome |
| `url` | `str` | Requested URL |
| `content` | `str \| None` | Response body (same as `html`) |
| `html` | `str \| None` | Response body |
| `status_code` | `int \| None` | HTTP status code |
| `error_message` | `str \| None` | Error detail |
| `response_time_ms` | `int` | Time to response |
| `retry_count` | `int` | Number of retries used |

**`ScraperStatus` enum:** `success`, `timeout`, `rate_limited`, `auth_required`, `captcha`, `error`

### `fetch_batch(urls) -> List[ScraperResult]`

Fetches multiple URLs concurrently, respecting `concurrent_requests` and `requests_per_second` settings.

```python
async with WebScraper() as scraper:
    results = await scraper.fetch_batch([url1, url2, url3])
```

### Static helpers

```python
from credentialing.scraper import WebScraper

soup = WebScraper.parse_html(html_string)          # → BeautifulSoup
rows = WebScraper.extract_table_data(html_string)  # → List[List[str]]
is_bot_wall = WebScraper._detect_captcha(html)     # → bool
```

---

## SeleniumScraper (`credentialing.scraper`)

For JavaScript-heavy pages. Lazy-initialized — only imports Selenium when first used.

```python
from credentialing.scraper import SeleniumScraper

scraper = SeleniumScraper()
html = await scraper.fetch_with_js(
    url="https://npdb.hrsa.gov/query",
    wait_selector="div.results",   # optional CSS selector to wait for
    wait_seconds=10,               # max wait
)
```

Requires `chromium` + `chromedriver` on the system PATH (included in the Docker image).

---

## CredentialingOrchestrator (`credentialing.orchestrator`)

Coordinates the full 4-stage pipeline.

### `process_provider(provider, sources=None) -> CredentialingTask`

```python
import asyncio
from credentialing.models import Provider
from credentialing.orchestrator import CredentialingOrchestrator

async def main():
    orchestrator = CredentialingOrchestrator()

    provider = Provider(
        first_name="John",
        last_name="Doe",
        npi="1234567890",
        state_code="CA"
    )

    task = await orchestrator.process_provider(
        provider,
        sources=["CA Medical Board", "OIG", "NPDB"]  # default if None
    )

    print(f"Status: {task.status}")
    print(f"Credentials: {len(task.credentials)}")
    print(f"Sanctions: {len(task.sanctions)}")
    print(f"Requires review: {task.normalized_data['summary']['requires_review']}")

asyncio.run(main())
```

The pipeline never raises — errors are caught and stored in `task.errors`. Always check `task.status`:

```python
from credentialing.models import ExtractionStatus

if task.status == ExtractionStatus.SUCCESS:
    report = task.normalized_data
elif task.status == ExtractionStatus.FAILED:
    print(task.errors)
```

---

## Configuration (`credentialing.config`)

```python
from credentialing.config import settings

print(settings.claude_model)           # "claude-3-5-sonnet-20241022"
print(settings.concurrent_requests)   # 4
print(settings.requests_per_second)   # 2.0
```

All settings are read from environment variables / `.env` at import time.

---

## Logging (`credentialing.logging_config`)

```python
from credentialing.logging_config import setup_logging, get_logger

setup_logging(log_level="INFO", log_format="text")  # call once at startup

logger = get_logger(__name__)
logger.info("my_event", provider_id="123", source="OIG")
```

`log_format="json"` produces machine-parseable structured logs (for production). `log_format="text"` produces colorized console output (for development).
