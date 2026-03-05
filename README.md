# Provider Credentialing Automation System

[![CI](https://github.com/rbalusup/provider-credentialing/actions/workflows/ci.yml/badge.svg)](https://github.com/rbalusup/provider-credentialing/actions/workflows/ci.yml)
[![Deploy AWS](https://github.com/rbalusup/provider-credentialing/actions/workflows/deploy-aws.yml/badge.svg)](https://github.com/rbalusup/provider-credentialing/actions/workflows/deploy-aws.yml)
[![Deploy GCP](https://github.com/rbalusup/provider-credentialing/actions/workflows/deploy-gcp.yml/badge.svg)](https://github.com/rbalusup/provider-credentialing/actions/workflows/deploy-gcp.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)

AI-powered healthcare provider credentialing system. Automates license verification, sanction checks, and credential normalization across medical boards, OIG, and NPDB using Claude AI + async web scraping.

**Repository:** https://github.com/rbalusup/provider-credentialing

---

## Overview

Verifying a provider's credentials is slow, manual, and error-prone. This system automates the entire pipeline:

1. **Fetch** — scrape state medical boards, OIG exclusion lists, and NPDB
2. **Extract** — use Claude to pull structured fields from raw HTML
3. **Detect** — flag sanctions, expired licenses, and red flags
4. **Normalize** — standardize dates, statuses, and license numbers into a clean report

### Supported Sources

| Source | Type | Method |
|--------|------|--------|
| California Medical Board | License verification | HTTP |
| OIG Exclusion List | Federal sanctions | HTTP |
| NPDB | National practitioner data | Selenium (JS-heavy) |

---

## Quick Start

### 1. Clone and install

```bash
git clone git@github.com:rbalusup/provider-credentialing.git
cd provider-credentialing

# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY
```

### 3. Run

```bash
# Single provider
uv run provider-credentialing credentialize \
    --first-name John --last-name Doe \
    --npi 1234567890 --state CA

# Check OIG exclusions only
uv run provider-credentialing check-exclusions \
    --first-name Jane --last-name Smith

# Batch process from CSV
uv run provider-credentialing batch-process examples/providers.csv

# Show all commands
uv run provider-credentialing --help
```

---

## Project Structure

```
provider-credentialing/
├── credentialing/
│   ├── models.py            # Pydantic data models
│   ├── config.py            # Settings from .env
│   ├── logging_config.py    # structlog setup
│   ├── scraper.py           # Async httpx scraper + Selenium fallback
│   ├── spiders.py           # Scrapy spiders (CA Board, OIG, NPDB)
│   ├── claude_extractor.py  # Claude API: extract, normalize, detect
│   ├── orchestrator.py      # 4-stage pipeline coordinator
│   └── cli.py               # typer CLI entry point
│
├── tests/                   # 53 tests, all external calls mocked
├── examples/                # Runnable demos + sample CSV
├── docs/
│   ├── ARCHITECTURE.md      # System design and data flow
│   ├── API.md               # Python API reference
│   └── DEPLOYMENT.md        # AWS + GCP deployment guide
│
├── .github/workflows/
│   ├── ci.yml               # Lint + test + docker build on every push
│   ├── deploy-aws.yml       # ECR + ECS Fargate on tag push
│   └── deploy-gcp.yml       # Artifact Registry + Cloud Run on tag push
│
├── Dockerfile               # Multi-stage, includes Chromium for Selenium
├── .env.example             # Environment variable template
└── CLAUDE.md                # Claude Code project instructions
```

---

## Configuration

All settings are loaded from `.env` (see `.env.example` for the full list):

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Claude API key |
| `CLAUDE_MODEL` | `claude-3-5-sonnet-20241022` | Model to use |
| `CRAWL_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `MAX_RETRIES` | `3` | Retry attempts per request |
| `REQUESTS_PER_SECOND` | `2` | Rate limit for scraping |
| `CONCURRENT_REQUESTS` | `4` | Parallel HTTP requests |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` |
| `LOG_FORMAT` | `json` | `json` (prod) or `text` (local dev) |

---

## CLI Reference

```
Commands:
  credentialize    Run full credentialing pipeline for one provider
  verify-license   Verify a specific license number
  check-exclusions Check OIG and sanction lists
  batch-process    Process multiple providers from a CSV file
  config-show      Display current configuration
```

### `credentialize`

```bash
uv run provider-credentialing credentialize \
  --first-name John \
  --last-name Doe \
  --npi 1234567890 \
  --state CA \
  --sources "CA Medical Board,OIG,NPDB" \
  --output-format json   # or "table"
```

### `batch-process` CSV format

```csv
first_name,last_name,npi,state
John,Doe,1234567890,CA
Jane,Smith,0987654321,NY
```

---

## Python API

```python
import asyncio
from credentialing.models import Provider
from credentialing.orchestrator import CredentialingOrchestrator

async def main():
    orchestrator = CredentialingOrchestrator()
    provider = Provider(
        first_name="John", last_name="Doe",
        npi="1234567890", state_code="CA"
    )
    task = await orchestrator.process_provider(
        provider, sources=["CA Medical Board", "OIG"]
    )
    print(task.normalized_data["summary"])

asyncio.run(main())
```

See [docs/API.md](docs/API.md) for the full reference.

---

## Development

```bash
# Run tests (53 tests, ~6s, no real API calls)
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=credentialing --cov-report=term-missing

# Lint
uv run ruff check credentialing/ tests/

# Format
uv run black credentialing/ tests/

# Type check
uv run mypy credentialing/ --ignore-missing-imports
```

### Adding a new data source

1. Add a spider in `credentialing/spiders.py` inheriting `BaseProviderSpider`
2. Add the source URL config in `orchestrator._extract_from_sources`
3. Add tests mocking the `_extract_from_sources` return value

---

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full AWS (ECS Fargate) and GCP (Cloud Run) instructions.

**TL;DR — push a tag to deploy:**

```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Roadmap

- [ ] FastAPI REST endpoint for programmatic access
- [ ] PostgreSQL persistence with audit trail
- [ ] Redis caching for repeated lookups
- [ ] Multi-state support (TX, FL, NY medical boards)
- [ ] HIPAA-compliant data handling mode
- [ ] Parallel batch processing with progress tracking

---

## License

MIT — see LICENSE file.