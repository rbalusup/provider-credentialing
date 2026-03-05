# Installation & Setup Guide

## Prerequisites

Ensure you have the following installed:

1. **Python 3.11 or higher**
   ```bash
   python --version
   ```

2. **UV Package Manager**
   ```bash
   # Install UV (single command)
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Or using pip
   pip install uv

   # Verify installation
   uv --version
   ```

3. **Anthropic API Key**
   - Get from https://console.anthropic.com
   - Required for Claude API integration

## Installation Steps

### 1. Clone/Create Project

```bash
# Navigate to project directory
cd provider_credentialing
```

### 2. Create Environment File

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API key
# ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 3. Install Dependencies with UV

```bash
# Install all dependencies
uv sync

# This will:
# - Create virtual environment
# - Install all dependencies from pyproject.toml
# - Install dev dependencies
```

### 4. Verify Installation

```bash
# Check Python version
uv run python --version

# Check installed packages
uv run pip list | grep anthropic

# Test CLI
uv run provider-credentialing --help
```

## Project Structure

```
provider_credentialing/
├── .env                              # Configuration (create from .env.example)
├── .env.example                      # Example configuration
├── pyproject.toml                    # Project metadata & dependencies
├── README.md                         # Main documentation
├── SETUP.md                          # This file
│
├── credentialing/                    # Main package
│   ├── __init__.py
│   ├── cli.py                        # CLI commands
│   ├── config.py                     # Configuration management
│   ├── logging_config.py             # Logging setup
│   ├── models.py                     # Data models
│   ├── claude_extractor.py           # Claude API integration
│   ├── scraper.py                    # Web scraping
│   ├── spiders.py                    # Scrapy spiders
│   └── orchestrator.py               # Pipeline orchestration
│
├── examples/                         # Example scripts & data
│   ├── usage_examples.py             # Usage examples
│   ├── providers.csv                 # Sample batch data
│   └── scrapy_settings.py            # Scrapy configuration
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_claude_extractor.py
│   ├── test_scraper.py
│   └── test_orchestrator.py
│
└── docs/                             # Documentation
    ├── API.md                        # API documentation
    ├── ARCHITECTURE.md               # System architecture
    └── DEPLOYMENT.md                 # Deployment guide
```

## Quick Start

### 1. Single Provider Credentialing

```bash
uv run provider-credentialing credentialize \
    --first-name John \
    --last-name Doe \
    --npi 1234567890 \
    --state CA
```

### 2. Check Exclusions

```bash
uv run provider-credentialing check-exclusions \
    --first-name Jane \
    --last-name Smith
```

### 3. Run Examples

```bash
# Run usage examples
uv run python examples/usage_examples.py

# Run with output to file
uv run python examples/usage_examples.py > examples/output.log
```

### 4. Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=credentialing

# Run specific test file
uv run pytest tests/test_models.py -v
```

## Configuration

### Environment Variables

Edit `.env` file:

```env
# Claude API
ANTHROPIC_API_KEY=sk-ant-your-key-here
CLAUDE_MODEL=claude-3-5-sonnet-20241022
MAX_TOKENS=2048
TEMPERATURE=0.0

# Web Crawling
CRAWL_TIMEOUT=30
MAX_RETRIES=3
REQUESTS_PER_SECOND=2
CONCURRENT_REQUESTS=4

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# System
DEBUG=false
ENVIRONMENT=development
```

## Development Workflow

### 1. Install Dev Dependencies

```bash
# Install includes dev dependencies
uv sync

# Or explicitly
uv sync --group dev
```

### 2. Code Formatting

```bash
# Format code with Black
uv run black credentialing/

# Format examples
uv run black examples/
```

### 3. Linting

```bash
# Check with Ruff
uv run ruff check credentialing/

# Auto-fix issues
uv run ruff check --fix credentialing/
```

### 4. Type Checking

```bash
# Check types with mypy
uv run mypy credentialing/
```

### 5. Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_models.py::test_provider_creation -v

# Run with coverage report
uv run pytest --cov=credentialing --cov-report=html
```

## Troubleshooting

### Issue: "command not found: uv"

**Solution**: Ensure UV is installed and in PATH
```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH (if needed)
export PATH="$HOME/.local/bin:$PATH"
```

### Issue: "ModuleNotFoundError: No module named 'anthropic'"

**Solution**: Reinstall dependencies
```bash
uv sync --force
```

### Issue: "ANTHROPIC_API_KEY not found"

**Solution**: Create and configure `.env` file
```bash
cp .env.example .env
# Edit .env and add your API key
cat .env | grep ANTHROPIC_API_KEY
```

### Issue: "Python version too old"

**Solution**: Update Python to 3.11+
```bash
# Check current version
python --version

# Install Python 3.11+ (macOS with Homebrew)
brew install python@3.11

# Or use pyenv
pyenv install 3.11.0
pyenv global 3.11.0
```

### Issue: Selenium/Browser automation not working

**Solution**: Install Chrome and Selenium
```bash
# macOS
brew install chromium

# Or use playwright
uv run playwright install
```

## Database Setup (Optional)

For production with PostgreSQL:

```bash
# Install PostgreSQL
brew install postgresql

# Create database
createdb provider_credentialing

# Update .env
DATABASE_URL=postgresql://user:password@localhost:5432/provider_credentialing
```

## Docker Setup (Optional)

```bash
# Build image
docker build -t provider-credentialing .

# Run container
docker run -e ANTHROPIC_API_KEY=sk-ant-xxx provider-credentialing
```

## Next Steps

1. **Read the README**: Full feature documentation
2. **Review Examples**: See `examples/usage_examples.py`
3. **Check Architecture**: Understand system design
4. **Explore CLI**: Run `uv run provider-credentialing --help`
5. **Review Tests**: See `tests/` directory

## Support & Documentation

- **Main Docs**: `README.md`
- **API Docs**: `docs/API.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Deployment**: `docs/DEPLOYMENT.md`

## Common Commands

```bash
# Show help
uv run provider-credentialing --help

# Show version
uv run provider-credentialing --version

# Run in debug mode
DEBUG=true uv run provider-credentialing credentialize ...

# Run with different log level
LOG_LEVEL=DEBUG uv run provider-credentialing ...

# Run with custom config
uv run python -c "from credentialing.config import settings; print(settings)"
```

## Success Indicators

✅ After successful setup:

1. `uv run provider-credentialing --help` works
2. `.env` file exists with API key
3. `uv run pytest` runs all tests
4. `uv run python examples/usage_examples.py` executes
5. No import errors when running commands

## Getting Help

If you encounter issues:

1. Check `.env` file configuration
2. Verify Python version (3.11+)
3. Try `uv sync --force` to reinstall
4. Check logs for error messages
5. Review example scripts for usage patterns