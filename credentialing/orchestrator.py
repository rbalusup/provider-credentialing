"""Orchestration service for provider credentialing pipeline."""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from credentialing.logging_config import get_logger
from credentialing.models import (
    Provider,
    CredentialingTask,
    ExtractionStatus,
    Credential,
    CredentialStatus,
    Sanction,
    SanctionStatus,
)
from credentialing.claude_extractor import ClaudeExtractor
from credentialing.scraper import WebScraper, SeleniumScraper

logger = get_logger(__name__)


class CredentialingOrchestrator:
    """Orchestrates the provider credentialing pipeline."""

    def __init__(self):
        """Initialize orchestrator."""
        self.claude_extractor = ClaudeExtractor()
        self.web_scraper = WebScraper()
        self._selenium_scraper: Optional[SeleniumScraper] = None

    @property
    def selenium_scraper(self) -> SeleniumScraper:
        """Lazy-initialize SeleniumScraper to avoid ImportError when selenium isn't installed."""
        if self._selenium_scraper is None:
            self._selenium_scraper = SeleniumScraper()
        return self._selenium_scraper

    async def process_provider(
            self,
            provider: Provider,
            sources: List[str] = None,
    ) -> CredentialingTask:
        """
        Process provider through full credentialing pipeline.

        Args:
            provider: Provider information
            sources: List of sources to check (e.g., ["CA Medical Board", "OIG", "NPDB"])

        Returns:
            CredentialingTask with results
        """
        if sources is None:
            sources = ["CA Medical Board", "OIG", "NPDB"]

        task = CredentialingTask(
            provider=provider,
            sources=sources,
            status=ExtractionStatus.IN_PROGRESS,
        )

        logger.info(
            "starting_credentialing_process",
            provider_id=provider.id,
            first_name=provider.first_name,
            last_name=provider.last_name,
            sources=sources,
        )

        try:
            # Stage 1: Fetch data from sources
            extraction_results = await self._extract_from_sources(
                provider,
                sources,
            )
            task.extraction_results = extraction_results

            # Stage 2: Extract structured data using Claude
            credentials = await self._extract_credentials(
                provider,
                extraction_results,
            )
            task.credentials = credentials

            # Stage 3: Check for sanctions/red flags
            sanctions = await self._check_sanctions(
                provider,
                extraction_results,
            )
            task.sanctions = sanctions

            # Stage 4: Normalize and validate
            normalized = await self._normalize_data(
                provider,
                credentials,
                sanctions,
            )
            task.normalized_data = normalized

            task.status = ExtractionStatus.SUCCESS
            task.updated_at = datetime.utcnow()

            logger.info(
                "credentialing_process_complete",
                provider_id=provider.id,
                status="success",
                credentials_found=len(credentials),
                sanctions_found=len(sanctions),
            )

        except Exception as e:
            task.status = ExtractionStatus.FAILED
            task.errors.append(str(e))
            task.updated_at = datetime.utcnow()

            logger.error(
                "credentialing_process_failed",
                provider_id=provider.id,
                error=str(e),
            )

        return task

    async def _extract_from_sources(
            self,
            provider: Provider,
            sources: List[str],
    ) -> List[Any]:
        """
        Extract data from multiple sources.

        Args:
            provider: Provider information
            sources: List of sources to check

        Returns:
            List of extraction results
        """
        logger.info("extracting_from_sources", provider_id=provider.id, sources=sources)

        results = []
        source_configs = {
            "CA Medical Board": {
                "urls": [
                    f"https://search.dca.ca.gov/cgi-bin/display.cgi"
                    f"?action=display&database=dca_file&query_type=PHRASE"
                    f"&query={provider.last_name}%2C+{provider.first_name}"
                ],
                "use_selenium": False,
            },
            "OIG": {
                "urls": [
                    f"https://exclusions.oig.hhs.gov/exclusions/search"
                    f"?name={provider.last_name}+{provider.first_name}"
                ],
                "use_selenium": False,
            },
            "NPDB": {
                "urls": ["https://npdb.hrsa.gov/query"],
                "use_selenium": True,  # NPDB requires JS
            },
        }

        for source in sources:
            if source not in source_configs:
                logger.warning("unknown_source", source=source)
                continue

            config = source_configs[source]

            try:
                if config.get("use_selenium"):
                    result = await self._fetch_with_selenium(
                        source,
                        config["urls"][0],
                    )
                else:
                    result = await self._fetch_with_http(
                        source,
                        config["urls"],
                    )

                if result:
                    results.append(result)

            except Exception as e:
                logger.error(
                    "source_extraction_failed",
                    source=source,
                    error=str(e),
                )
                continue

        return results

    async def _fetch_with_http(
            self,
            source_name: str,
            urls: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Fetch data using HTTP client."""
        async with self.web_scraper as scraper:
            results = await scraper.fetch_batch(urls)

            successful = [r for r in results if r.status.value == "success"]

            if successful:
                logger.info(
                    "http_fetch_success",
                    source=source_name,
                    successful_urls=len(successful),
                )
                return {
                    "source": source_name,
                    "urls": urls,
                    "html_content": successful[0].html,
                    "status": "success",
                }
            else:
                logger.warning("http_fetch_failed", source=source_name)
                return None

    async def _fetch_with_selenium(
            self,
            source_name: str,
            url: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch data using Selenium for JS-heavy sites."""
        html = await self.selenium_scraper.fetch_with_js(url)

        if html:
            logger.info("selenium_fetch_success", source=source_name)
            return {
                "source": source_name,
                "url": url,
                "html_content": html,
                "status": "success",
            }
        else:
            logger.warning("selenium_fetch_failed", source=source_name)
            return None

    async def _extract_credentials(
            self,
            provider: Provider,
            extraction_results: List[Any],
    ) -> List[Credential]:
        """
        Extract credential data using Claude.

        Args:
            provider: Provider information
            extraction_results: Raw extraction results

        Returns:
            List of extracted credentials
        """
        logger.info(
            "extracting_credentials",
            provider_id=provider.id,
            sources_count=len(extraction_results),
        )

        credentials = []

        for result in extraction_results:
            try:
                source = result.get("source")
                html_content = result.get("html_content", "")

                # Extract provider info using Claude
                extraction = self.claude_extractor.extract_provider_info(html_content)

                if extraction.get("success"):
                    extracted_data = extraction.get("data", {})

                    # Create credential record
                    credential = Credential(
                        provider_id=str(provider.id) if provider.id else "unknown",
                        credential_type="license",
                        issuing_authority=source,
                        credential_number=extracted_data.get("license_number"),
                        issue_date=extracted_data.get("issue_date"),
                        expiration_date=extracted_data.get("expiration_date"),
                        status=CredentialStatus(
                            extracted_data.get("license_status", "unknown")
                        ),
                        source_url=result.get("url", ""),
                        verified_at=datetime.utcnow(),
                    )

                    credentials.append(credential)

                    logger.info(
                        "credential_extracted",
                        provider_id=provider.id,
                        source=source,
                        credential_number=credential.credential_number,
                    )

            except Exception as e:
                logger.error(
                    "credential_extraction_error",
                    provider_id=provider.id,
                    source=result.get("source"),
                    error=str(e),
                )

        return credentials

    async def _check_sanctions(
            self,
            provider: Provider,
            extraction_results: List[Any],
    ) -> List[Sanction]:
        """
        Check for sanctions and red flags.

        Args:
            provider: Provider information
            extraction_results: Raw extraction results

        Returns:
            List of sanctions/red flags
        """
        logger.info("checking_sanctions", provider_id=provider.id)

        sanctions = []
        provider_data = {
            "first_name": provider.first_name,
            "last_name": provider.last_name,
            "npi": provider.npi,
            "license_number": provider.license_number,
            "state": provider.state_code,
        }

        # Use Claude to detect sanctions
        detection_result = self.claude_extractor.detect_sanctions(provider_data)

        if detection_result.get("success"):
            result_data = detection_result.get("data", {})
            red_flags = result_data.get("red_flags", [])

            if red_flags:
                for flag in red_flags:
                    sanction = Sanction(
                        provider_id=str(provider.id) if provider.id else "unknown",
                        sanction_type="red_flag",
                        description=flag,
                        status=SanctionStatus.UNKNOWN,
                        source="AI Analysis",
                        verified_at=datetime.utcnow(),
                    )
                    sanctions.append(sanction)

                logger.warning(
                    "red_flags_detected",
                    provider_id=provider.id,
                    flag_count=len(red_flags),
                )

        return sanctions

    async def _normalize_data(
            self,
            provider: Provider,
            credentials: List[Credential],
            sanctions: List[Sanction],
    ) -> Dict[str, Any]:
        """
        Normalize and validate all extracted data.

        Args:
            provider: Provider information
            credentials: Extracted credentials
            sanctions: Detected sanctions

        Returns:
            Normalized data dictionary
        """
        logger.info(
            "normalizing_data",
            provider_id=provider.id,
            credentials_count=len(credentials),
            sanctions_count=len(sanctions),
        )

        normalized = {
            "provider": provider.model_dump(),
            "credentials": [c.model_dump() for c in credentials],
            "sanctions": [s.model_dump() for s in sanctions],
            "summary": {
                "total_credentials": len(credentials),
                "active_credentials": sum(
                    1 for c in credentials if c.status == CredentialStatus.ACTIVE
                ),
                "expired_credentials": sum(
                    1 for c in credentials if c.status == CredentialStatus.EXPIRED
                ),
                "sanctions_found": len(sanctions),
                "requires_review": len(sanctions) > 0 or any(
                    c.status != CredentialStatus.ACTIVE for c in credentials
                ),
            },
            "normalized_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            "normalization_complete",
            provider_id=provider.id,
            requires_review=normalized["summary"]["requires_review"],
        )

        return normalized