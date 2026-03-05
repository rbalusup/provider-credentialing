"""Tests for web scraping utilities."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from credentialing.scraper import WebScraper, ScraperResult, ScraperStatus


# ---------------------------------------------------------------------------
# ScraperResult
# ---------------------------------------------------------------------------

class TestScraperResult:
    def test_default_values(self):
        result = ScraperResult(status=ScraperStatus.SUCCESS, url="https://example.com")
        assert result.content is None
        assert result.html is None
        assert result.error_message is None
        assert result.retry_count == 0
        assert result.response_time_ms == 0
        assert result.status_code is None

    def test_full_construction(self):
        result = ScraperResult(
            status=ScraperStatus.SUCCESS,
            url="https://example.com",
            content="<html></html>",
            html="<html></html>",
            status_code=200,
            response_time_ms=150,
            retry_count=1,
        )
        assert result.status == ScraperStatus.SUCCESS
        assert result.status_code == 200
        assert result.response_time_ms == 150


# ---------------------------------------------------------------------------
# WebScraper — static / sync helpers
# ---------------------------------------------------------------------------

class TestParseHtml:
    def test_returns_soup(self):
        html = "<html><body><p>Hello</p></body></html>"
        soup = WebScraper.parse_html(html)
        assert soup.find("p").text == "Hello"

    def test_empty_string(self):
        soup = WebScraper.parse_html("")
        assert soup is not None


class TestExtractTableData:
    def test_basic_table(self):
        html = """
        <table>
            <tr><th>Name</th><th>Status</th></tr>
            <tr><td>John Doe</td><td>Active</td></tr>
        </table>
        """
        rows = WebScraper.extract_table_data(html)
        assert len(rows) == 2
        assert rows[0] == ["Name", "Status"]
        assert rows[1] == ["John Doe", "Active"]

    def test_no_tables(self):
        html = "<html><body><p>No tables here.</p></body></html>"
        rows = WebScraper.extract_table_data(html)
        assert rows == []

    def test_multiple_tables(self):
        html = """
        <table><tr><td>A</td></tr></table>
        <table><tr><td>B</td></tr></table>
        """
        rows = WebScraper.extract_table_data(html)
        assert len(rows) == 2


class TestDetectCaptcha:
    def test_recaptcha_detected(self):
        html = "<html><body>Please solve the reCAPTCHA to continue.</body></html>"
        assert WebScraper._detect_captcha(html) is True

    def test_hcaptcha_detected(self):
        html = "<html><body>hCaptcha challenge required.</body></html>"
        assert WebScraper._detect_captcha(html) is True

    def test_no_captcha(self):
        html = "<html><body>Provider license details for Dr. Smith.</body></html>"
        assert WebScraper._detect_captcha(html) is False

    def test_case_insensitive(self):
        html = "<html><body>CAPTCHA REQUIRED</body></html>"
        assert WebScraper._detect_captcha(html) is True


class TestGetRetryAfter:
    def test_numeric_header(self):
        response = MagicMock()
        response.headers = {"Retry-After": "30"}
        assert WebScraper._get_retry_after(response) == 30

    def test_missing_header_returns_default(self):
        response = MagicMock()
        response.headers = {}
        assert WebScraper._get_retry_after(response) == 5

    def test_non_numeric_header_returns_default(self):
        response = MagicMock()
        response.headers = {"Retry-After": "Wed, 21 Oct 2024 07:28:00 GMT"}
        assert WebScraper._get_retry_after(response) == 5


# ---------------------------------------------------------------------------
# WebScraper — async fetch
# ---------------------------------------------------------------------------

class TestWebScraperFetch:
    @pytest.mark.asyncio
    async def test_context_manager_sets_client(self):
        async with WebScraper() as scraper:
            assert scraper.client is not None
        # After exit, client is closed (aclose was called)

    @pytest.mark.asyncio
    async def test_fetch_without_context_raises(self):
        scraper = WebScraper()
        with pytest.raises(RuntimeError, match="not initialized"):
            await scraper.fetch("https://example.com")

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>content</html>"
        mock_response.raise_for_status = MagicMock()

        async with WebScraper() as scraper:
            scraper.client.get = AsyncMock(return_value=mock_response)
            result = await scraper.fetch("https://example.com")

        assert result.status == ScraperStatus.SUCCESS
        assert result.content == "<html>content</html>"
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_fetch_auth_required_401(self):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        async with WebScraper() as scraper:
            scraper.client.get = AsyncMock(return_value=mock_response)
            result = await scraper.fetch("https://example.com")

        assert result.status == ScraperStatus.AUTH_REQUIRED

    @pytest.mark.asyncio
    async def test_fetch_captcha_detected(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "Please complete the reCAPTCHA to continue."
        mock_response.raise_for_status = MagicMock()

        async with WebScraper() as scraper:
            scraper.client.get = AsyncMock(return_value=mock_response)
            result = await scraper.fetch("https://example.com")

        assert result.status == ScraperStatus.CAPTCHA

    @pytest.mark.asyncio
    async def test_fetch_http_error(self):
        import httpx

        async with WebScraper() as scraper:
            scraper.client.get = AsyncMock(
                side_effect=httpx.HTTPError("Connection refused")
            )
            result = await scraper.fetch("https://example.com")

        assert result.status == ScraperStatus.ERROR
        assert "Connection refused" in result.error_message


class TestWebScraperFetchBatch:
    @pytest.mark.asyncio
    async def test_fetch_batch_returns_all_results(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>ok</html>"
        mock_response.raise_for_status = MagicMock()

        urls = ["https://example.com/a", "https://example.com/b"]

        async with WebScraper() as scraper:
            scraper.client.get = AsyncMock(return_value=mock_response)
            results = await scraper.fetch_batch(urls)

        assert len(results) == 2
        assert all(r.status == ScraperStatus.SUCCESS for r in results)