# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

AI-powered healthcare provider credentialing system. Python 3.12, managed with `uv`.

**Repository:** https://github.com/rbalusup/provider-credentialing

**Core idea:** Given a provider's name/NPI/license, crawl medical board sites + OIG/NPDB, extract structured credential data using Claude, detect sanctions, and normalize everything into a report.

## Architecture

```
credentialing/
  models.py           # Pydantic data models (Provider, Credential, Sanction, ...)
  config.py           # Settings loaded from .env via pydantic-settings
  logging_config.py   # structlog structured logging setup
  scraper.py          # Async httpx scraper + Selenium fallback for JS-heavy sites
  spiders.py          # Scrapy spiders (CA Medical Board, OIG, NPDB)
  claude_extractor.py # Claude API calls for extraction, normalization, sanction detection
  orchestrator.py     # 4-stage pipeline: fetch → extract → sanctions → normalize
  cli.py              # typer CLI entry point

tests/
  test_models.py
  test_claude_extractor.py  # All Anthropic API calls are mocked
  test_scraper.py
  test_orchestrator.py

examples/
  usage_examples.py   # Runnable demos for each component
  providers.csv       # Sample input for batch processing
```

## Commands

```bash
# Install all dependencies (including dev)
uv sync

# Run tests
uv run pytest tests/ -v

# Run tests with coverage
uv run pytest tests/ --cov=credentialing --cov-report=term-missing

# Run the CLI
uv run provider-credentialing credentialize --first-name John --last-name Doe --state CA

# Verify a license
uv run provider-credentialing verify-license --license-number MD123456 --state CA

# Check exclusions
uv run provider-credentialing check-exclusions --first-name John --last-name Doe

# Batch process from CSV
uv run provider-credentialing batch-process examples/providers.csv

# Show current config
uv run provider-credentialing config-show

# Run usage examples (requires ANTHROPIC_API_KEY)
uv run python examples/usage_examples.py

# Add a dependency
uv add <package>

# Add a dev dependency
uv add --dev <package>

# Lint / format
uv run ruff check credentialing/ tests/
uv run black credentialing/ tests/

# Type check
uv run mypy credentialing/
```

## Environment Setup

Copy `.env.example` to `.env` and fill in:

```bash
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-3-5-sonnet-20241022   # default
LOG_LEVEL=INFO
LOG_FORMAT=json       # or "text" for local dev
DEBUG=false
```

## Key Conventions

- **Async throughout**: scraper and orchestrator are fully async; use `asyncio.run()` only at the CLI boundary.
- **Structured logging**: always use `get_logger(__name__)` from `credentialing.logging_config`; pass data as keyword args: `logger.info("event_name", key=value)`.
- **Tenacity retries**: Claude API calls and HTTP fetches use `@retry` decorators — don't add manual retry loops.
- **Mock external calls in tests**: all `Anthropic` client calls must be mocked; never make real API calls in tests.
- **Enum comparisons**: use `task.status == ExtractionStatus.SUCCESS`, never `str(task.status) == "..."`.
- **SeleniumScraper**: lazy-initialized in the orchestrator; only instantiated when actually needed.

## Known Warnings (non-breaking, do not fix unless asked)

- `datetime.utcnow()` is deprecated in Python 3.12+ — spread throughout models/orchestrator.
- Pydantic v2: class-based `Config` is deprecated (use `model_config = ConfigDict(...)`).

## Adding New Data Sources

1. Add a new spider in `spiders.py` inheriting from `BaseProviderSpider`.
2. Add the source config (URL template, `use_selenium` flag) to `_extract_from_sources` in `orchestrator.py`.
3. Write tests mocking `_extract_from_sources` return value.