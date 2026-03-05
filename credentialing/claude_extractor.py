"""Claude API integration for intelligent data extraction and normalization."""

import json
import time
from typing import Dict, Any, List
from anthropic import Anthropic, APIError, RateLimitError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from credentialing.logging_config import get_logger
from credentialing.config import settings

logger = get_logger(__name__)


class ClaudeExtractor:
    """Intelligent data extraction using Claude API."""

    def __init__(self):
        """Initialize Claude client."""
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        self.max_tokens = settings.max_tokens

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((RateLimitError, APIError)),
    )
    def extract_provider_info(self, html_content: str) -> Dict[str, Any]:
        """
        Extract provider information from HTML content using Claude.

        Args:
            html_content: HTML content from medical board website

        Returns:
            Extracted provider information
        """
        start_time = time.time()

        prompt = f"""
        Extract provider credential information from the following HTML content.
        
        Return ONLY valid JSON with the following structure (no other text):
        {{
            "first_name": "string or null",
            "last_name": "string or null",
            "middle_name": "string or null",
            "npi": "string or null",
            "license_number": "string or null",
            "specialty": "string or null",
            "license_status": "active|inactive|expired|suspended|revoked|unknown",
            "issue_date": "YYYY-MM-DD or null",
            "expiration_date": "YYYY-MM-DD or null",
            "confidence": {{"first_name": 0-1, "license_number": 0-1, ...}}
        }}
        
        HTML Content:
        {html_content[:4000]}
        """

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.temperature,
            )

            response_text = response.content[0].text.strip()

            # Try to extract JSON from response
            json_data = self._parse_json_response(response_text)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "provider_extraction_success",
                processing_time_ms=processing_time,
                fields_extracted=len(json_data),
            )

            return {
                "success": True,
                "data": json_data,
                "processing_time_ms": processing_time,
                "raw_response": response_text,
            }

        except (RateLimitError, APIError) as e:
            logger.warning(
                "claude_api_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(
                "provider_extraction_failed",
                error=str(e),
                processing_time_ms=processing_time,
            )
            return {
                "success": False,
                "error": str(e),
                "processing_time_ms": processing_time,
            }

    def normalize_credential_data(
            self,
            raw_data: Dict[str, Any],
            source_name: str,
    ) -> Dict[str, Any]:
        """
        Normalize extracted credential data using Claude.

        Args:
            raw_data: Raw extracted data
            source_name: Name of data source (e.g., "CA Medical Board")

        Returns:
            Normalized credential data
        """
        start_time = time.time()

        prompt = f"""
        Normalize the following provider credential data extracted from {source_name}.
        
        Apply these rules:
        1. Standardize date formats to YYYY-MM-DD
        2. Standardize license status to: active, inactive, expired, suspended, revoked, unknown
        3. Extract NPI if present
        4. Validate license number format for the state
        5. Flag any data quality issues
        
        Return ONLY valid JSON with this structure:
        {{
            "normalized_data": {{}},
            "data_quality_issues": ["issue1", "issue2"],
            "requires_manual_review": true|false,
            "confidence_score": 0-1
        }}
        
        Raw Data:
        {json.dumps(raw_data, indent=2)[:3000]}
        """

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.temperature,
            )

            response_text = response.content[0].text.strip()
            json_data = self._parse_json_response(response_text)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "data_normalization_success",
                source=source_name,
                processing_time_ms=processing_time,
            )

            return {
                "success": True,
                "data": json_data,
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(
                "normalization_failed",
                error=str(e),
                processing_time_ms=processing_time,
            )
            return {
                "success": False,
                "error": str(e),
                "processing_time_ms": processing_time,
            }

    def detect_sanctions(
            self,
            provider_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze provider data to detect potential sanctions or red flags.

        Args:
            provider_data: Provider information

        Returns:
            Sanction detection results
        """
        start_time = time.time()

        prompt = f"""
        Analyze the following provider data for potential sanctions, red flags, or compliance issues.
        
        Consider:
        1. License status (suspended, revoked, etc.)
        2. Expired credentials
        3. Multiple state licenses
        4. Gaps in employment history
        5. Unusual data patterns
        
        Return ONLY valid JSON:
        {{
            "red_flags": ["flag1", "flag2"],
            "sanction_risk_score": 0-1,
            "requires_investigation": true|false,
            "investigation_notes": "explanation"
        }}
        
        Provider Data:
        {json.dumps(provider_data, indent=2)[:2000]}
        """

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.temperature,
            )

            response_text = response.content[0].text.strip()
            json_data = self._parse_json_response(response_text)

            processing_time = int((time.time() - start_time) * 1000)

            logger.info(
                "sanction_detection_complete",
                processing_time_ms=processing_time,
            )

            return {
                "success": True,
                "data": json_data,
                "processing_time_ms": processing_time,
            }

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(
                "sanction_detection_failed",
                error=str(e),
                processing_time_ms=processing_time,
            )
            return {
                "success": False,
                "error": str(e),
                "processing_time_ms": processing_time,
            }

    @staticmethod
    def _parse_json_response(response_text: str) -> Dict[str, Any]:
        """
        Parse JSON from Claude response, handling markdown code blocks.

        Args:
            response_text: Raw response from Claude

        Returns:
            Parsed JSON data
        """
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]

        response_text = response_text.strip()
        return json.loads(response_text)

    def batch_extract_providers(
            self,
            providers_html: List[tuple[str, str]],  # (provider_id, html_content)
    ) -> List[Dict[str, Any]]:
        """
        Extract information for multiple providers sequentially.

        Args:
            providers_html: List of (provider_id, html_content) tuples

        Returns:
            List of extraction results
        """
        results = []

        for provider_id, html_content in providers_html:
            logger.info("extracting_provider", provider_id=provider_id)

            result = self.extract_provider_info(html_content)
            result["provider_id"] = provider_id
            results.append(result)

        logger.info("batch_extraction_complete", total_providers=len(results))
        return results