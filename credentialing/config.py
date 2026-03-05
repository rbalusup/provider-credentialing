"""Configuration management for provider credentialing system."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Claude API
    anthropic_api_key: str
    claude_model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 2048
    temperature: float = 0.0

    # Database
    database_url: str = "sqlite:///./provider_credentialing.db"
    redis_url: str = "redis://localhost:6379/0"

    # Web Crawling
    crawl_timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 2
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    # Rate Limiting
    requests_per_second: float = 2.0
    concurrent_requests: int = 4

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Feature Flags
    enable_browser_automation: bool = True
    enable_parallel_processing: bool = True
    enable_caching: bool = True

    # System
    debug: bool = False
    environment: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()


settings = get_settings()