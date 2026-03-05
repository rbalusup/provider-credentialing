# Local Testing Guide

How to run the application against **real provider names and real data sources** on your local machine (macOS or Windows).

---

## What this does

When you run the CLI with a real provider name, the system:

1. Fetches the provider's license page from the California Medical Board (or other configured sources)
2. Sends the raw HTML to Claude, which extracts structured fields (name, license number, status, dates)
3. Runs a sanction detection pass through Claude against the provider's profile
4. Returns a normalized credentialing report in table or JSON format

Real network calls are made to live websites. Results depend on whether the source is accessible, whether a CAPTCHA is served, and whether the provider exists in that database.

---

## Prerequisites

### macOS

```bash
# 1. Python 3.12
brew install python@3.12

# 2. uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Chrome (needed only for NPDB — skippable for CA Medical Board + OIG)
brew install --cask google-chrome
```

### Windows

```powershell
# 1. Install uv (run in PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Verify
uv --version

# 3. Chrome — download from https://www.google.com/chrome/
```

> Chrome is only required if you include `NPDB` as a source. For `CA Medical Board` and `OIG` it is not needed.

---

## One-time setup

### 1. Clone and install

```bash
# macOS / Windows (Git Bash or PowerShell)
git clone git@github.com:rbalusup/provider-credentialing.git
cd provider-credentialing
uv sync
```

### 2. Create your `.env` file

```bash
# macOS / Git Bash
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

Open `.env` and set your real Anthropic API key:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...your-real-key-here...

# Recommended for local dev — human-readable output instead of JSON
LOG_FORMAT=text
LOG_LEVEL=INFO
```

Get your key from [console.anthropic.com](https://console.anthropic.com) → API Keys → Create Key.

### 3. Verify setup

```bash
uv run provider-credentialing --help
```

You should see the list of available commands. If you see a `ValidationError` about `ANTHROPIC_API_KEY`, your `.env` file is missing or the key is not set.

---

## Running with a real provider

### Single provider — table output (default)

```bash
uv run provider-credentialing credentialize \
    --first-name John \
    --last-name Doe \
    --state CA \
    --sources "CA Medical Board,OIG"
```

```
# Windows PowerShell
uv run provider-credentialing credentialize `
    --first-name John `
    --last-name Doe `
    --state CA `
    --sources "CA Medical Board,OIG"
```

**What you'll see:**

```
Provider Credentialing System
Checking: John Doe (NPI: None)

┌─────────────────────────────────────────────┐
│ Provider Information                        │
│ Name  │ John Doe                            │
│ NPI   │ Not provided                        │
│ State │ CA                                  │
└─────────────────────────────────────────────┘

Credentials Found
┌────────┬────────────────────┬───────────┬────────┬────────────┐
│ Type   │ Authority          │ Number    │ Status │ Expiration │
│ license│ CA Medical Board   │ MD123456  │ active │ 2027-12-31 │
└────────┴────────────────────┴───────────┴────────┴────────────┘

Summary
│ Total Credentials  │ 1   │
│ Active Credentials │ 1   │
│ Sanctions Found    │ 0   │
│ Requires Review    │ No  │
```

### Single provider — JSON output

```bash
uv run provider-credentialing credentialize \
    --first-name John \
    --last-name Doe \
    --state CA \
    --sources "CA Medical Board,OIG" \
    --output-format json
```

Useful when piping results to another tool or saving to a file:

```bash
# macOS
uv run provider-credentialing credentialize \
    --first-name John --last-name Doe --state CA \
    --output-format json > results/john_doe.json

# Windows PowerShell
uv run provider-credentialing credentialize `
    --first-name John --last-name Doe --state CA `
    --output-format json | Out-File results\john_doe.json
```

### With NPI number (improves accuracy)

```bash
uv run provider-credentialing credentialize \
    --first-name Jane \
    --last-name Smith \
    --npi 1234567890 \
    --state CA \
    --sources "CA Medical Board,OIG"
```

### OIG exclusion check only

Quick check — is this provider on the federal exclusion list?

```bash
uv run provider-credentialing check-exclusions \
    --first-name John \
    --last-name Doe
```

---

## Choosing sources

| Source | Requires Chrome | What it checks |
|--------|-----------------|----------------|
| `CA Medical Board` | No | CA physician/surgeon license status |
| `OIG` | No | Federal exclusion from Medicare/Medicaid |
| `NPDB` | **Yes** | National Practitioner Data Bank (malpractice, adverse actions) |

Start with `CA Medical Board,OIG` for a quick check without needing Chrome:

```bash
--sources "CA Medical Board,OIG"
```

Add `NPDB` once you have Chrome installed:

```bash
--sources "CA Medical Board,OIG,NPDB"
```

---

## Batch processing (multiple providers)

### 1. Create your CSV

Edit `examples/providers.csv` or create a new file:

```csv
first_name,last_name,npi,state
Jane,Smith,1234567890,CA
Robert,Johnson,0987654321,CA
Maria,Garcia,1111111111,CA
```

Required columns: `first_name`, `last_name`, `state`
Optional: `npi` (improves match accuracy)

### 2. Run batch processing

```bash
uv run provider-credentialing batch-process examples/providers.csv \
    --sources "CA Medical Board,OIG"
```

Results are saved automatically to `examples/providers_results.json`.

---

## Debug mode — see what's happening

Set `LOG_LEVEL=DEBUG` in your `.env` (or inline) to see every HTTP request, Claude prompt, and extracted field:

```bash
# macOS
LOG_LEVEL=DEBUG LOG_FORMAT=text uv run provider-credentialing credentialize \
    --first-name John --last-name Doe --state CA

# Windows PowerShell
$env:LOG_LEVEL="DEBUG"; $env:LOG_FORMAT="text"
uv run provider-credentialing credentialize `
    --first-name John --last-name Doe --state CA
```

---

## Local Docker run (macOS and Windows)

You can also run the full application inside Docker, which mirrors the production environment exactly.

### 1. Build the image

```bash
docker build -t provider-credentialing:local .
```

### 2. Run the CLI via Docker

```bash
# macOS (reads .env file)
docker run --rm --env-file .env \
    provider-credentialing:local \
    credentialize --first-name John --last-name Doe --state CA

# Windows PowerShell
docker run --rm --env-file .env `
    provider-credentialing:local `
    credentialize --first-name John --last-name Doe --state CA
```

### 3. Batch process a CSV file via Docker

Mount the `examples/` directory so Docker can read and write files:

```bash
# macOS
docker run --rm --env-file .env \
    -v "$(pwd)/examples:/app/examples" \
    provider-credentialing:local \
    batch-process examples/providers.csv --sources "CA Medical Board,OIG"

# Windows PowerShell
docker run --rm --env-file .env `
    -v "${PWD}\examples:/app/examples" `
    provider-credentialing:local `
    batch-process examples/providers.csv --sources "CA Medical Board,OIG"
```

---

## Understanding the output

### Status values

| `task.status` | Meaning |
|---------------|---------|
| `success` | All stages completed; results are reliable |
| `failed` | Pipeline crashed (check `task.errors`) |
| `partial` | Some sources succeeded; others failed |

### Credential status

| Status | Meaning |
|--------|---------|
| `active` | License is current and valid |
| `expired` | License has passed its expiration date |
| `suspended` | License temporarily suspended |
| `revoked` | License permanently revoked |
| `unknown` | Could not determine status from source |

### `requires_review: true` means

- At least one credential is not `active`, **or**
- At least one sanction or red flag was detected

Always manually verify before making credentialing decisions.

---

## Common issues and fixes

### "ANTHROPIC_API_KEY not found" / ValidationError

```bash
# Confirm .env has the key
grep ANTHROPIC_API_KEY .env
```

If `.env` doesn't exist: `cp .env.example .env` then add your key.

### HTTP fetch returns `auth_required` or `error`

Medical board websites occasionally block automated requests or change their URLs. Try:
- Increasing the delay: set `REQUESTS_PER_SECOND=1` in `.env`
- Checking the URL directly in your browser to confirm the site is reachable

### `captcha` status returned

The source detected a bot challenge. Options:
1. Wait a few minutes and retry (many sites reset after a short cooldown)
2. Switch to `--sources "OIG"` (OIG rarely serves CAPTCHAs)
3. Enable Selenium: set `ENABLE_BROWSER_AUTOMATION=true` in `.env`

### Selenium / Chrome errors (NPDB source)

```bash
# macOS — install Chromium
brew install --cask chromium

# Confirm chromedriver is on PATH
chromedriver --version
```

On Windows, download ChromeDriver from [chromedriver.chromium.org](https://chromedriver.chromium.org/) matching your Chrome version and add it to your `PATH`.

### No credentials returned (empty table)

This usually means the provider was not found in the source database, or the HTML structure returned by the site didn't match Claude's extraction. Try:
- Verifying the provider exists by searching the source site directly in your browser
- Adding `--output-format json` to see the full `task.errors` and `extraction_results`

### Windows: `uv` not found after install

Restart your terminal, or add uv to PATH manually:

```powershell
$env:PATH += ";$env:USERPROFILE\.local\bin"
```

---

## Verifying your config

```bash
uv run provider-credentialing config-show
```

This prints all active settings (API key is masked as `***`). Confirm:
- `anthropic_api_key` shows `***` (set correctly)
- `log_format` is `text` for readable local output
- `enable_browser_automation` is `true` if you want NPDB support

---

## End-to-end local checklist

```
[ ] uv sync ran without errors
[ ] .env exists and ANTHROPIC_API_KEY is set to a real key
[ ] uv run provider-credentialing --help shows commands
[ ] uv run provider-credentialing config-show shows *** for the API key
[ ] Single provider run returns a results table (even if empty)
[ ] (Optional) Chrome installed for NPDB source
[ ] (Optional) Docker image builds with: docker build -t provider-credentialing:local .
```