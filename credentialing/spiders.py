"""Scrapy spiders for crawling medical board and licensing authority websites."""

import scrapy
from scrapy import Request
from typing import Optional, Dict, Any
from urllib.parse import urljoin, quote
from credentialing.logging_config import get_logger

logger = get_logger(__name__)


class BaseProviderSpider(scrapy.Spider):
    """Base spider for provider credentialing data sources."""

    name = "base_provider_spider"
    allowed_domains = []
    start_urls = []
    custom_settings = {
        "CONCURRENT_REQUESTS": 4,
        "DOWNLOAD_DELAY": 2,
        "ROBOTSTXT_OBEY": True,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ),
        "COOKIES_ENABLED": True,
        "REDIRECT_ENABLED": True,
        "RETRY_TIMES": 3,
        "RETRY_HTTP_CODES": [500, 502, 503, 504, 408, 429],
    }

    def __init__(self, *args, **kwargs):
        """Initialize spider with logging."""
        super().__init__(*args, **kwargs)
        self.logger_context = get_logger(self.name)

    def start_requests(self):
        """Generate initial requests."""
        for url in self.start_urls:
            yield Request(
                url,
                callback=self.parse,
                errback=self.errback_httpbin,
                dont_obey_robotstxt=False,
            )

    def errback_httpbin(self, failure):
        """Handle request errors."""
        self.logger_context.error(
            "request_failed",
            url=failure.request.url,
            error=str(failure.value),
        )

    def parse(self, response):
        """Parse response - override in subclasses."""
        raise NotImplementedError("Subclasses must implement parse method")


class CaliforniaLicenseVerificationSpider(BaseProviderSpider):
    """Spider for California Medical Board license verification."""

    name = "ca_medical_board"
    allowed_domains = ["search.dca.ca.gov"]

    # Example URLs - in production, these would be parameterized
    # Based on the CA Medical Board search form
    start_urls = [
        "https://search.dca.ca.gov/cgi-bin/display.cgi?action=display&database=dca_file&search_type=STARTS&results_per_page=100&sort=RELEVANCE&query_type=PHRASE",
    ]

    def __init__(self, first_name: str = "", last_name: str = "", *args, **kwargs):
        """Initialize with search parameters."""
        super().__init__(*args, **kwargs)
        self.first_name = first_name
        self.last_name = last_name

    def start_requests(self):
        """Generate search requests for provider."""
        # Build search URL with parameters
        search_url = (
            f"https://search.dca.ca.gov/cgi-bin/display.cgi"
            f"?action=display&database=dca_file&search_type=STARTS"
            f"&results_per_page=100&sort=RELEVANCE"
            f"&query_type=PHRASE"
            f"&query={quote(f'{self.last_name}, {self.first_name}')}"
        )

        yield Request(
            search_url,
            callback=self.parse,
            errback=self.errback_httpbin,
            meta={"provider_name": f"{self.first_name} {self.last_name}"},
        )

    def parse(self, response):
        """Parse California Medical Board search results."""
        provider_name = response.meta.get("provider_name", "Unknown")

        self.logger_context.info(
            "parsing_ca_results",
            provider_name=provider_name,
            status_code=response.status,
        )

        # Extract provider records
        provider_rows = response.css("tr.odd, tr.even")

        for row in provider_rows:
            try:
                # Extract data from table cells
                cells = row.css("td")
                if len(cells) >= 5:
                    yield {
                        "source": "CA Medical Board",
                        "url": response.url,
                        "name": cells[0].css("::text").get("").strip(),
                        "license_type": cells[1].css("::text").get("").strip(),
                        "license_number": cells[2].css("::text").get("").strip(),
                        "status": cells[3].css("::text").get("").strip(),
                        "expiration": cells[4].css("::text").get("").strip(),
                        "detail_url": urljoin(response.url, cells[0].css("a::attr(href)").get("")),
                    }
            except Exception as e:
                self.logger_context.error(
                    "parse_error",
                    provider=provider_name,
                    error=str(e),
                )
                continue

    def parse_detail(self, response):
        """Parse detailed license information page."""
        yield {
            "source": "CA Medical Board",
            "url": response.url,
            "full_name": response.css("h1::text").get("").strip(),
            "license_number": response.css("p:contains('License Number')::text").get("").strip(),
            "status": response.css("p:contains('License Status')::text").get("").strip(),
            "issue_date": response.css("p:contains('Issued')::text").get("").strip(),
            "expiration_date": response.css("p:contains('Expiration')::text").get("").strip(),
            "specialty": response.css("p:contains('Specialty')::text").get("").strip(),
            "education": response.css("p:contains('Education')::text").get("").strip(),
        }


class FederalOIGExclusionSpider(BaseProviderSpider):
    """Spider for OIG exclusion list verification."""

    name = "oig_exclusion_check"
    allowed_domains = ["exclusions.oig.hhs.gov"]

    start_urls = [
        "https://exclusions.oig.hhs.gov/exclusions/search",
    ]

    def __init__(self, last_name: str = "", first_name: str = "", *args, **kwargs):
        """Initialize with search parameters."""
        super().__init__(*args, **kwargs)
        self.first_name = first_name
        self.last_name = last_name

    def start_requests(self):
        """Generate search requests to OIG exclusion database."""
        search_url = (
            f"https://exclusions.oig.hhs.gov/exclusions/search"
            f"?name={quote(self.last_name + ' ' + self.first_name)}"
        )

        yield Request(
            search_url,
            callback=self.parse,
            errback=self.errback_httpbin,
            meta={"provider_name": f"{self.first_name} {self.last_name}"},
        )

    def parse(self, response):
        """Parse OIG exclusion search results."""
        provider_name = response.meta.get("provider_name", "Unknown")

        self.logger_context.info(
            "checking_oig_exclusions",
            provider_name=provider_name,
        )

        # Check if provider is found in exclusion list
        exclusion_found = response.css("div.exclusion-record")

        if not exclusion_found:
            yield {
                "source": "OIG Exclusions",
                "provider_name": provider_name,
                "url": response.url,
                "status": "NOT_FOUND",
                "message": "Provider not found in exclusion list",
            }
        else:
            for record in exclusion_found:
                yield {
                    "source": "OIG Exclusions",
                    "provider_name": provider_name,
                    "url": response.url,
                    "status": "SANCTIONED",
                    "exclusion_type": record.css("::attr(data-exclusion-type)").get(""),
                    "exclusion_date": record.css("::attr(data-exclusion-date)").get(""),
                    "details": record.css("::text").get("").strip(),
                }


class NPDBLicenseSpider(BaseProviderSpider):
    """Spider for National Practitioner Data Bank (NPDB) queries."""

    name = "npdb_verification"
    allowed_domains = ["npdb.hrsa.gov"]

    def __init__(self, license_number: str = "", state: str = "", *args, **kwargs):
        """Initialize with search parameters."""
        super().__init__(*args, **kwargs)
        self.license_number = license_number
        self.state = state

    def start_requests(self):
        """Generate NPDB queries."""
        # NPDB queries typically require authentication and special handling
        # This is a simplified example
        search_url = (
            f"https://npdb.hrsa.gov/query"
            f"?license={quote(self.license_number)}"
            f"&state={quote(self.state)}"
        )

        yield Request(
            search_url,
            callback=self.parse,
            errback=self.errback_httpbin,
            meta={
                "license_number": self.license_number,
                "state": self.state,
            },
        )

    def parse(self, response):
        """Parse NPDB response."""
        license_number = response.meta.get("license_number")
        state = response.meta.get("state")

        self.logger_context.info(
            "querying_npdb",
            license_number=license_number,
            state=state,
        )

        # Extract data from NPDB response
        yield {
            "source": "NPDB",
            "license_number": license_number,
            "state": state,
            "url": response.url,
            "query_results": response.css("div.query-results::text").get("").strip(),
            "verification_status": "verified" if response.status == 200 else "failed",
        }