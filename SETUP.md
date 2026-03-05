# Setup Guide

Step-by-step instructions for local development, Docker, and CI/CD configuration.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | `brew install python@3.12` or [python.org](https://python.org) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Git | any | `brew install git` |
| Docker | 24+ | [docker.com](https://www.docker.com/get-started/) *(optional, for container builds)* |
| Anthropic API key | — | [console.anthropic.com](https://console.anthropic.com) |

---

## Local Development Setup

### 1. Clone the repository

```bash
git clone git@github.com:rbalusup/provider-credentialing.git
cd provider-credentialing
```

### 2. Create your environment file

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

> `.env` is gitignored — it will never be committed.

### 3. Install dependencies

```bash
uv sync        # installs all deps including dev tools
```

uv automatically creates a `.venv` and resolves from `uv.lock` for reproducible installs.

### 4. Verify the setup

```bash
uv run provider-credentialing --help     # CLI works
uv run pytest tests/ -q                  # 53 tests pass
```

---

## Development Workflow

### Running the CLI

```bash
# Single provider
uv run provider-credentialing credentialize \
    --first-name John --last-name Doe --state CA

# Show current config
uv run provider-credentialing config-show

# Batch processing
uv run provider-credentialing batch-process examples/providers.csv
```

### Running tests

```bash
uv run pytest tests/ -v                              # all tests, verbose
uv run pytest tests/test_models.py -v                # one file
uv run pytest tests/ --cov=credentialing             # with coverage
uv run pytest tests/ --cov=credentialing \
    --cov-report=html                                # HTML report → htmlcov/
```

### Linting and formatting

```bash
uv run ruff check credentialing/ tests/              # lint
uv run ruff check --fix credentialing/ tests/        # auto-fix
uv run black credentialing/ tests/ examples/         # format
uv run mypy credentialing/ --ignore-missing-imports  # type check
```

### Adding dependencies

```bash
uv add httpx                  # production dependency
uv add --dev pytest-mock      # dev-only dependency
```

---

## Docker

### Build the image

```bash
docker build -t provider-credentialing:local .
```

### Run the CLI via Docker

```bash
docker run --rm \
    -e ANTHROPIC_API_KEY=sk-ant-xxx \
    provider-credentialing:local \
    credentialize --first-name John --last-name Doe --state CA
```

### Run with a `.env` file

```bash
docker run --rm \
    --env-file .env \
    provider-credentialing:local \
    config-show
```

### Docker image details

- **Base:** `python:3.12-slim`
- **Multi-stage build** — builder installs deps, runtime copies only the venv
- **Chromium included** — required by `SeleniumScraper` for JS-heavy sites
- **Non-root user** — runs as `appuser` for security

---

## CI/CD Overview

Three GitHub Actions workflows are in `.github/workflows/`:

| Workflow | File | Trigger |
|----------|------|---------|
| CI (lint + test + docker build) | `ci.yml` | Every push to `main`/`develop`, every PR |
| Deploy to AWS ECS Fargate | `deploy-aws.yml` | Tag push (`v*.*.*`) or manual |
| Deploy to GCP Cloud Run | `deploy-gcp.yml` | Tag push (`v*.*.*`) or manual |

### Secrets required in GitHub → Settings → Secrets

**For AWS:**

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | IAM user access key with ECR + ECS permissions |
| `AWS_SECRET_ACCESS_KEY` | IAM user secret key |
| `ANTHROPIC_API_KEY` | Injected into ECS task at runtime |

**For GCP:**

| Secret | Description |
|--------|-------------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | WIF provider URI (keyless auth) |
| `GCP_SERVICE_ACCOUNT` | Service account email for deployments |

The `ANTHROPIC_API_KEY` for GCP is stored in **Secret Manager** (not a GitHub secret) and referenced as `anthropic-api-key:latest` in the workflow. This is the recommended approach.

### Release a new version

```bash
# Bump version in pyproject.toml, then:
git add pyproject.toml
git commit -m "chore: bump version to v1.1.0"
git tag v1.1.0
git push origin main --tags
```

Both deploy workflows will trigger automatically.

---

## Environment Details

### `.env` variables

See `.env.example` for the full list. Key variables:

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | **Required.** Your Claude API key |
| `CLAUDE_MODEL` | Model ID (default: `claude-3-5-sonnet-20241022`) |
| `LOG_FORMAT` | `json` for production, `text` for local dev |
| `ENVIRONMENT` | `development` / `staging` / `production` |
| `ENABLE_BROWSER_AUTOMATION` | `true` enables Selenium for JS-heavy sites |

### Python version

The project pins Python 3.12 in `.python-version`. uv respects this automatically.

---

## Troubleshooting

### `command not found: uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"   # add to ~/.zshrc or ~/.bashrc
```

### `ANTHROPIC_API_KEY not found` or `ValidationError`

```bash
# Confirm .env exists and has the key
grep ANTHROPIC_API_KEY .env
```

### `ModuleNotFoundError`

```bash
uv sync --force    # force-reinstall all dependencies
```

### Selenium / ChromeDriver issues

```bash
# macOS
brew install chromium

# Linux (in Docker)
# Already handled in the Dockerfile (apt-get install chromium chromium-driver)
```

### Tests failing with real network calls

All tests mock external calls. If you see real HTTP requests in tests, a mock is missing. Check that the test patches `credentialing.claude_extractor.Anthropic` and `credentialing.scraper.WebScraper`.

---

## Useful One-liners

```bash
# Check config loaded from .env
uv run python -c "from credentialing.config import settings; print(settings.model_dump())"

# Run examples (requires valid ANTHROPIC_API_KEY)
uv run python examples/usage_examples.py

# Watch tests on file change (requires watchdog)
uv run ptw tests/ credentialing/

# Generate HTML coverage report
uv run pytest tests/ --cov=credentialing --cov-report=html && open htmlcov/index.html
```