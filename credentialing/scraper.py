"""Web scraping utilities with resilience and error handling."""

import asyncio
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from credentialing.logging_config import get_logger
from credentialing.config import settings

logger = get_logger(__name__)


class ScraperStatus(str, Enum):
    """Status of scraping operation."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    AUTH_REQUIRED = "auth_required"
    CAPTCHA = "captcha"
    ERROR = "error"


@dataclass
class ScraperResult:
    """Result of scraping operation."""
    status: ScraperStatus
    url: str
    content: Optional[str] = None
    html: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    response_time_ms: int = 0
    status_code: Optional[int] = None


class WebScraper:
    """Web scraper with resilience, retry logic, and anti-bot handling."""

    def __init__(self):
        """Initialize web scraper."""
        self.client = None
        self.user_agent = settings.user_agent
        self.timeout = settings.crawl_timeout
        self.max_retries = settings.max_retries
        self.retry_delay = settings.retry_delay

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, asyncio.TimeoutError)),
    )
    async def fetch(self, url: str) -> ScraperResult:
        """
        Fetch URL with retry logic and error handling.

        Args:
            url: URL to fetch

        Returns:
            ScraperResult with content and status
        """
        if not self.client:
            raise RuntimeError("Scraper not initialized. Use 'async with' context.")

        start_time = time.time()
        retry_count = 0

        try:
            logger.info("fetching_url", url=url)

            response = await self.client.get(url)

            # Check for rate limiting
            if response.status_code == 429:
                logger.warning("rate_limited", url=url, retry_after=response.headers.get("Retry-After"))
                await asyncio.sleep(self._get_retry_after(response))
                raise httpx.HTTPStatusError("Rate limited", request=response.request, response=response)

            # Check for authentication required
            if response.status_code in [401, 403]:
                logger.warning("auth_required", url=url)
                return ScraperResult(
                    status=ScraperStatus.AUTH_REQUIRED,
                    url=url,
                    status_code=response.status_code,
                    error_message="Authentication required",
                    response_time_ms=int((time.time() - start_time) * 1000),
                )

            # Check for CAPTCHA
            if self._detect_captcha(response.text):
                logger.warning("captcha_detected", url=url)
                return ScraperResult(
                    status=ScraperStatus.CAPTCHA,
                    url=url,
                    status_code=response.status_code,
                    error_message="CAPTCHA challenge detected",
                    response_time_ms=int((time.time() - start_time) * 1000),
                )

            response.raise_for_status()

            logger.info(
                "fetch_success",
                url=url,
                status_code=response.status_code,
                content_length=len(response.text),
            )

            return ScraperResult(
                status=ScraperStatus.SUCCESS,
                url=url,
                content=response.text,
                html=response.text,
                status_code=response.status_code,
                response_time_ms=int((time.time() - start_time) * 1000),
                retry_count=retry_count,
            )

        except asyncio.TimeoutError:
            response_time = int((time.time() - start_time) * 1000)
            logger.error("fetch_timeout", url=url, timeout_ms=response_time)
            return ScraperResult(
                status=ScraperStatus.TIMEOUT,
                url=url,
                error_message=f"Timeout after {self.timeout}s",
                response_time_ms=response_time,
                retry_count=retry_count,
            )

        except httpx.HTTPError as e:
            response_time = int((time.time() - start_time) * 1000)
            logger.error(
                "fetch_error",
                url=url,
                error=str(e),
                response_time_ms=response_time,
            )
            return ScraperResult(
                status=ScraperStatus.ERROR,
                url=url,
                error_message=str(e),
                response_time_ms=response_time,
                retry_count=retry_count,
            )

    async def fetch_batch(self, urls: List[str]) -> List[ScraperResult]:
        """
        Fetch multiple URLs concurrently with rate limiting.

        Args:
            urls: List of URLs to fetch

        Returns:
            List of ScraperResults
        """
        results = []
        semaphore = asyncio.Semaphore(settings.concurrent_requests)

        async def fetch_with_limit(url: str):
            async with semaphore:
                await asyncio.sleep(1.0 / settings.requests_per_second)
                return await self.fetch(url)

        tasks = [fetch_with_limit(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        successful = sum(1 for r in results if r.status == ScraperStatus.SUCCESS)
        logger.info(
            "batch_fetch_complete",
            total_urls=len(urls),
            successful=successful,
            failed=len(urls) - successful,
        )

        return results

    @staticmethod
    def parse_html(html_content: str) -> BeautifulSoup:
        """
        Parse HTML content with BeautifulSoup.

        Args:
            html_content: HTML content string

        Returns:
            BeautifulSoup object
        """
        return BeautifulSoup(html_content, "html.parser")

    @staticmethod
    def extract_table_data(html_content: str) -> List[Dict[str, str]]:
        """
        Extract table data from HTML.

        Args:
            html_content: HTML content string

        Returns:
            List of dictionaries with table data
        """
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")

        all_rows = []
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                all_rows.append([cell.get_text(strip=True) for cell in cells])

        return all_rows

    @staticmethod
    def _detect_captcha(response_text: str) -> bool:
        """
        Detect CAPTCHA challenges in response.

        Args:
            response_text: Response HTML content

        Returns:
            True if CAPTCHA detected
        """
        captcha_indicators = [
            "recaptcha",
            "hcaptcha",
            "captcha",
            "challenge",
            "security check",
            "verify you are human",
        ]

        response_lower = response_text.lower()
        return any(indicator in response_lower for indicator in captcha_indicators)

    @staticmethod
    def _get_retry_after(response: httpx.Response) -> int:
        """
        Get retry delay from response headers.

        Args:
            response: HTTP response

        Returns:
            Retry delay in seconds
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return int(retry_after)
            except ValueError:
                pass

        return 5  # Default 5 second wait


class SeleniumScraper:
    """Web scraper using Selenium for JavaScript-heavy sites."""

    def __init__(self):
        """Initialize Selenium scraper."""
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            self.webdriver = webdriver
            self.By = By
            self.WebDriverWait = WebDriverWait
            self.EC = EC
            self.driver = None
        except ImportError:
            logger.error("selenium_not_installed")
            raise

    async def fetch_with_js(
            self,
            url: str,
            wait_selector: Optional[str] = None,
            wait_seconds: int = 10,
    ) -> Optional[str]:
        """
        Fetch URL and wait for JavaScript to render.

        Args:
            url: URL to fetch
            wait_selector: CSS selector to wait for
            wait_seconds: Maximum wait time

        Returns:
            Rendered HTML or None
        """
        try:
            from selenium.webdriver.chrome.options import Options

            logger.info("fetching_with_selenium", url=url)

            options = Options()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"user-agent={settings.user_agent}")

            self.driver = self.webdriver.Chrome(options=options)

            self.driver.get(url)

            # Wait for element if specified
            if wait_selector:
                self.WebDriverWait(self.driver, wait_seconds).until(
                    self.EC.presence_of_element_located((self.By.CSS_SELECTOR, wait_selector))
                )

            return self.driver.page_source

        except Exception as e:
            logger.error("selenium_fetch_error", url=url, error=str(e))
            return None

        finally:
            if self.driver:
                self.driver.quit()