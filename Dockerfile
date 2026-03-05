# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies into /app/.venv
RUN uv sync --frozen --no-dev

# ── Runtime stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Chrome + ChromeDriver for Selenium (needed by SeleniumScraper)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

WORKDIR /app

# Copy venv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY credentialing/ ./credentialing/
COPY examples/  ./examples/
COPY hello.py   ./

# Make venv the active Python
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Non-root user for security
RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

# Default: run the CLI (override in ECS task / Cloud Run job command)
ENTRYPOINT ["provider-credentialing"]
CMD ["--help"]