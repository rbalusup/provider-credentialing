# Provider Credentialing Automation System

A production-ready Python system for automated healthcare provider credentialing, verification, and sanctions checking using Claude AI and advanced web scraping.

## 🎯 Overview

This system automates the complex process of verifying provider credentials across multiple data sources:

- **Medical Board Licenses**: State medical boards (CA, TX, FL, etc.)
- **Federal Exclusions**: OIG Exclusion List, NPDB
- **Professional Credentials**: Board certifications, DEA registrations
- **Sanctions Checks**: Malpractice, licensing suspensions, revocations

### Key Features

✅ **AI-Powered Extraction**: Claude API for intelligent data extraction and normalization
✅ **Resilient Web Crawling**: Scrapy + Selenium for handling complex, dynamic websites
✅ **Anti-Bot Handling**: CAPTCHA detection, rate limiting, retry logic
✅ **Production-Grade**: Structured logging, error handling, async processing
✅ **Extensible Architecture**: Plugin-based data sources, modular design
✅ **Batch Processing**: CSV import for processing multiple providers
✅ **CLI Interface**: Easy-to-use command-line tools

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                  CLI Interface                      │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│            Credentialing Orchestrator                │
│  (Coordinates entire pipeline)                      │
└──────┬───────────────┬──────────────┬────────────────┘
       │               │              │
  ┌────▼────┐   ┌─────▼────┐   ┌──────▼───┐
  │Web      │   │Claude    │   │Validation│
  │Scraper  │   │Extractor │   │& Normali-│
  │(HTTP +  │   │          │   │zation    │
  │Selenium)│   │          │   │          │
  └────┬────┘   └─────┬────┘   └──────┬───┘
       │              │              │
  ┌────▼──────────────▼──────────────▼────┐
  │         Data Models & Storage          │
  │  (Providers, Credentials, Sanctions)   │
  └────────────────────────────────────────┘
```

## 📦 Installation

### Prerequisites

- Python 3.11+
- `uv` package manager (https://docs.astral.sh/uv/)
- API key from Anthropic (for Claude API)
- Optional: Chrome/Chromium (for Selenium)

### Setup

1. **Clone or create project directory**:
```bash
cd provider_credentialing
```

2. **Copy environment file**:
```bash
cp .env.example .env
```

3. **Add your Anthropic API key**:
```bash
# Edit .env and add your API key
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

4. **Install dependencies with UV**:
```bash
uv sync
```

5. **Verify installation**:
```bash
uv run provider-credentialing --help
```

## 🚀 Quick Start

### Single Provider Credentialing

```bash
uv run provider-credentialing credentialize \
    --first-name John \
    --last-name Doe \
    --npi 1234567890 \
    --state CA
```

### Check OIG Exclusions

```bash
uv run provider-credentialing check-exclusions \
    --first-name Jane \
    --last-name Smith
```

### Batch Processing

```bash
# Create CSV file (see examples/providers.csv)
uv run provider-credentialing batch-process \
    examples/providers.csv \
    --sources "CA Medical Board,OIG,NPDB"
```

### View Configuration

```bash
uv run provider-credentialing config-show
```

## 📝 Configuration

### Environment Variables

Create a `.env` file with the following settings:

```env
# Claude API
ANTHROPIC_API_KEY=sk-ant-your-key
CLAUDE_MODEL=claude-3-5-sonnet-20241022
MAX_TOKENS=2048
TEMPERATURE=0.0

# Web Crawling
CRAWL_TIMEOUT=30
MAX_RETRIES=3
RETRY_DELAY=2
REQUESTS_PER_SECOND=2
CONCURRENT_REQUESTS=4

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Feature Flags
ENABLE_BROWSER_AUTOMATION=true
ENABLE_PARALLEL_PROCESSING=true
ENABLE_CACHING=true
```

## 🏗️ Project Structure

```
provider_credentialing/
├── credentialing/
│   ├── __init__.py
│   ├── cli.py                 # CLI commands
│   ├── config.py              # Configuration management
│   ├── logging_config.py       # Structured logging setup
│   ├── models.py              # Data models
│   ├── claude_extractor.py    # Claude AI integration
│   ├── scraper.py             # Web scraping utilities
│   ├── spiders.py             # Scrapy spider definitions
│   └── orchestrator.py        # Pipeline orchestration
├── examples/
│   └── providers.csv          # Example batch input
├── tests/
│   ├── test_models.py
│   ├── test_claude_extractor.py
│   ├── test_scraper.py
│   └── test_orchestrator.py
├── pyproject.toml             # Project dependencies
├── .env.example               # Example environment file
├── README.md                  # This file
└── LICENSE
```

## 💡 Key Components

### 1. **Data Models** (`credentialing/models.py`)

Pydantic models for type safety:

- `Provider`: Provider information
- `Credential`: License/certification records
- `Sanction`: Sanctions and red flags
- `CredentialingTask`: Full pipeline state
- `ExtractionResult`: Raw data extraction results

### 2. **Claude Extractor** (`credentialing/claude_extractor.py`)

Intelligent data extraction using Claude API:

```python
from credentialing.claude_extractor import ClaudeExtractor

extractor = ClaudeExtractor()

# Extract provider info from HTML
result = extractor.extract_provider_info(html_content)

# Normalize data
normalized = extractor.normalize_credential_data(raw_data, "CA Medical Board")

# Detect sanctions/red flags
sanctions = extractor.detect_sanctions(provider_data)
```

### 3. **Web Scraper** (`credentialing/scraper.py`)

Resilient web scraper with async support:

```python
from credentialing.scraper import WebScraper
import asyncio

async def fetch_data():
    async with WebScraper() as scraper:
        result = await scraper.fetch("https://example.com")

        # Handle results
        if result.status.value == "success":
            html = result.html
        elif result.status.value == "captcha":
            # CAPTCHA detected
            pass

asyncio.run(fetch_data())
```

### 4. **Orchestrator** (`credentialing/orchestrator.py`)

Coordinates the entire credentialing pipeline:

```python
from credentialing.orchestrator import CredentialingOrchestrator
from credentialing.models import Provider
import asyncio

async def process_provider():
    orchestrator = CredentialingOrchestrator()

    provider = Provider(
        first_name="John",
        last_name="Doe",
        npi="1234567890",
        state_code="CA"
    )

    task = await orchestrator.process_provider(
        provider,
        sources=["CA Medical Board", "OIG", "NPDB"]
    )

    return task

result = asyncio.run(process_provider())
```

## 🔄 Data Pipeline

### 1. **Data Extraction**
- Fetch HTML/content from medical boards and licensing authorities
- Handle authentication, rate limiting, CAPTCHA
- Extract raw data using Scrapy or direct HTTP

### 2. **Intelligent Extraction**
- Use Claude API to extract structured fields
- Confidence scores for each extracted field
- Handle variations in data format

### 3. **Normalization**
- Standardize date formats (YYYY-MM-DD)
- Normalize credential status
- Validate license numbers

### 4. **Sanctions Detection**
- Analyze for red flags
- Check federal exclusion lists
- Identify potential compliance issues

### 5. **Output & Storage**
- Generate credentialing report
- Store results with audit trail
- Flag for manual review if needed

## 📊 Example Output

```json
{
  "status": "success",
  "provider": {
    "first_name": "John",
    "last_name": "Doe",
    "npi": "1234567890",
    "state_code": "CA"
  },
  "credentials": [
    {
      "credential_type": "license",
      "issuing_authority": "CA Medical Board",
      "credential_number": "MD123456",
      "status": "active",
      "expiration_date": "2026-12-31"
    }
  ],
  "sanctions": [],
  "normalized_data": {
    "summary": {
      "total_credentials": 1,
      "active_credentials": 1,
      "sanctions_found": 0,
      "requires_review": false
    }
  }
}
```

## 🧪 Testing

Run tests with pytest:

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=credentialing

# Specific test file
uv run pytest tests/test_models.py -v
```

## 🔐 Security Considerations

### API Key Management
- Never commit `.env` file
- Rotate keys regularly
- Use environment variables in production

### Data Privacy
- Implement proper access controls
- Audit trail for all data access
- HIPAA compliance (if applicable)

### Web Scraping
- Respect `robots.txt`
- Rate limiting to avoid overwhelming servers
- Proper user-agent identification
- Handle anti-bot measures responsibly

## 🚨 Error Handling

The system handles various failure modes:

```python
from credentialing.scraper import ScraperStatus

# Results include status codes
- SUCCESS: Page fetched successfully
- TIMEOUT: Request exceeded timeout
- RATE_LIMITED: 429 Too Many Requests
- AUTH_REQUIRED: 401/403 authentication needed
- CAPTCHA: CAPTCHA challenge detected
- ERROR: General HTTP/connection error
```

## 🔧 Advanced Usage

### Custom Data Sources

Add new data sources by implementing spiders:

```python
# In credentialing/spiders.py
class CustomBoardSpider(BaseProviderSpider):
    name = "custom_board"
    allowed_domains = ["custom.state.gov"]

    def start_requests(self):
        # Generate requests
        pass

    def parse(self, response):
        # Extract data
        yield {...}
```

### Custom Claude Prompts

Modify extraction prompts for specific domains:

```python
# In credentialing/claude_extractor.py
custom_prompt = f"""
Extract the following fields from {source_name}:
...
"""
```

## 📈 Performance Tips

1. **Batch Processing**: Process multiple providers concurrently
2. **Caching**: Enable Redis caching for frequently accessed data
3. **Rate Limiting**: Adjust `REQUESTS_PER_SECOND` based on targets
4. **Async Operations**: Leverage async/await for I/O-bound operations

## 🐛 Troubleshooting

### API Key Not Found
```bash
# Verify .env file exists and has valid key
cat .env | grep ANTHROPIC_API_KEY
```

### Installation Issues
```bash
# Ensure Python 3.11+
python --version

# Reinstall dependencies
uv sync --force
```

### CAPTCHA Detection
- Enable Selenium for JavaScript-heavy sites
- Implement proper delays between requests
- Consider using browser automation service

## 📚 Dependencies

Key libraries used:

| Library | Purpose |
|---------|---------|
| `anthropic` | Claude API integration |
| `scrapy` | Web scraping framework |
| `selenium` | Browser automation |
| `httpx` | Async HTTP client |
| `pydantic` | Data validation |
| `structlog` | Structured logging |
| `typer` | CLI framework |

## 📄 License

MIT License - See LICENSE file

## 🤝 Contributing

1. Create feature branch
2. Add tests for new features
3. Ensure all tests pass
4. Submit pull request

## 📞 Support

For issues and questions:
- Check README troubleshooting section
- Review example scripts in `examples/`
- Check project documentation

## 🗓️ Roadmap

- [ ] PostgreSQL integration
- [ ] Redis caching layer
- [ ] Web API (FastAPI)
- [ ] Parallel batch processing
- [ ] Database persistence
- [ ] Enhanced CAPTCHA handling
- [ ] Multi-state support
- [ ] Compliance reporting

## 🎓 Interview Talking Points

This project demonstrates:

✅ **Production AI Systems**: Claude API integration with error handling
✅ **Web Automation**: Scrapy + Selenium for resilient scraping
✅ **Healthcare Data**: Provider credentialing domain knowledge
✅ **System Design**: Multi-stage pipeline with async processing
✅ **Data Quality**: Normalization, validation, audit trails
✅ **Python Expertise**: Modern Python (3.11+), async/await, type hints
✅ **Observability**: Structured logging, error tracking