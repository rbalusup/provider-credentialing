"""Tests for CredentialingOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from credentialing.models import (
    Provider,
    Credential,
    CredentialStatus,
    ExtractionStatus,
    SanctionStatus,
)
from credentialing.orchestrator import CredentialingOrchestrator


@pytest.fixture
def provider():
    return Provider(
        id="test_123",
        first_name="John",
        last_name="Doe",
        npi="1234567890",
        state_code="CA",
    )


@pytest.fixture
def orchestrator():
    """Return an orchestrator with SeleniumScraper patched out."""
    with patch("credentialing.orchestrator.SeleniumScraper"):
        with patch("credentialing.orchestrator.ClaudeExtractor"):
            orch = CredentialingOrchestrator()
            return orch


# ---------------------------------------------------------------------------
# process_provider
# ---------------------------------------------------------------------------

class TestProcessProvider:
    @pytest.mark.asyncio
    async def test_successful_pipeline(self, orchestrator, provider):
        mock_extraction_result = {
            "source": "CA Medical Board",
            "html_content": "<html>license info</html>",
            "status": "success",
            "url": "https://example.com",
        }
        extracted_credential_data = {
            "first_name": "John",
            "last_name": "Doe",
            "license_number": "MD123456",
            "license_status": "active",
        }
        sanction_data = {
            "red_flags": [],
            "sanction_risk_score": 0.0,
            "requires_investigation": False,
            "investigation_notes": "Clear",
        }

        orchestrator._extract_from_sources = AsyncMock(return_value=[mock_extraction_result])
        orchestrator.claude_extractor.extract_provider_info = MagicMock(
            return_value={"success": True, "data": extracted_credential_data}
        )
        orchestrator.claude_extractor.detect_sanctions = MagicMock(
            return_value={"success": True, "data": sanction_data}
        )

        task = await orchestrator.process_provider(provider, ["CA Medical Board"])

        assert task.status == ExtractionStatus.SUCCESS
        assert len(task.credentials) == 1
        assert task.credentials[0].credential_number == "MD123456"
        assert task.credentials[0].status == CredentialStatus.ACTIVE
        assert len(task.sanctions) == 0

    @pytest.mark.asyncio
    async def test_red_flags_create_sanctions(self, orchestrator, provider):
        mock_extraction_result = {
            "source": "OIG",
            "html_content": "<html>exclusion data</html>",
            "status": "success",
            "url": "https://oig.example.com",
        }
        sanction_data = {
            "red_flags": ["Excluded from Medicare", "License expired"],
            "sanction_risk_score": 0.9,
            "requires_investigation": True,
            "investigation_notes": "High risk",
        }

        orchestrator._extract_from_sources = AsyncMock(return_value=[mock_extraction_result])
        orchestrator.claude_extractor.extract_provider_info = MagicMock(
            return_value={"success": False, "error": "Parse error"}
        )
        orchestrator.claude_extractor.detect_sanctions = MagicMock(
            return_value={"success": True, "data": sanction_data}
        )

        task = await orchestrator.process_provider(provider, ["OIG"])

        assert task.status == ExtractionStatus.SUCCESS
        assert len(task.sanctions) == 2
        for sanction in task.sanctions:
            assert sanction.sanction_type == "red_flag"

    @pytest.mark.asyncio
    async def test_extraction_exception_marks_failed(self, orchestrator, provider):
        orchestrator._extract_from_sources = AsyncMock(
            side_effect=Exception("Network failure")
        )

        task = await orchestrator.process_provider(provider)

        assert task.status == ExtractionStatus.FAILED
        assert len(task.errors) == 1
        assert "Network failure" in task.errors[0]

    @pytest.mark.asyncio
    async def test_default_sources_used_when_none_given(self, orchestrator, provider):
        orchestrator._extract_from_sources = AsyncMock(return_value=[])
        orchestrator.claude_extractor.detect_sanctions = MagicMock(
            return_value={"success": True, "data": {"red_flags": []}}
        )

        task = await orchestrator.process_provider(provider)

        assert task.sources == ["CA Medical Board", "OIG", "NPDB"]

    @pytest.mark.asyncio
    async def test_task_has_normalized_data(self, orchestrator, provider):
        orchestrator._extract_from_sources = AsyncMock(return_value=[])
        orchestrator.claude_extractor.detect_sanctions = MagicMock(
            return_value={"success": True, "data": {"red_flags": []}}
        )

        task = await orchestrator.process_provider(provider, ["CA Medical Board"])

        assert task.normalized_data is not None
        assert "summary" in task.normalized_data
        assert "provider" in task.normalized_data


# ---------------------------------------------------------------------------
# _normalize_data
# ---------------------------------------------------------------------------

class TestNormalizeData:
    @pytest.mark.asyncio
    async def test_summary_counts(self, orchestrator, provider):
        credentials = [
            Credential(
                provider_id="test_123",
                credential_type="license",
                issuing_authority="CA Medical Board",
                credential_number="MD123456",
                status=CredentialStatus.ACTIVE,
            ),
            Credential(
                provider_id="test_123",
                credential_type="license",
                issuing_authority="DEA",
                credential_number="DEA999",
                status=CredentialStatus.EXPIRED,
            ),
        ]
        sanctions = []

        result = await orchestrator._normalize_data(provider, credentials, sanctions)

        summary = result["summary"]
        assert summary["total_credentials"] == 2
        assert summary["active_credentials"] == 1
        assert summary["expired_credentials"] == 1
        assert summary["sanctions_found"] == 0
        assert summary["requires_review"] is True  # expired credential

    @pytest.mark.asyncio
    async def test_requires_review_when_sanctions_present(self, orchestrator, provider):
        from credentialing.models import Sanction

        sanctions = [
            Sanction(
                provider_id="test_123",
                sanction_type="red_flag",
                description="Excluded from Medicare",
                status=SanctionStatus.SANCTIONED,
                source="OIG",
            )
        ]

        result = await orchestrator._normalize_data(provider, [], sanctions)

        assert result["summary"]["requires_review"] is True
        assert result["summary"]["sanctions_found"] == 1

    @pytest.mark.asyncio
    async def test_no_review_needed_for_all_active(self, orchestrator, provider):
        credentials = [
            Credential(
                provider_id="test_123",
                credential_type="license",
                issuing_authority="CA Medical Board",
                status=CredentialStatus.ACTIVE,
            )
        ]

        result = await orchestrator._normalize_data(provider, credentials, [])

        assert result["summary"]["requires_review"] is False


# ---------------------------------------------------------------------------
# _fetch_with_http
# ---------------------------------------------------------------------------

class TestFetchWithHttp:
    @pytest.mark.asyncio
    async def test_returns_none_on_all_failures(self, orchestrator):
        from credentialing.scraper import ScraperStatus, ScraperResult

        mock_result = ScraperResult(
            status=ScraperStatus.ERROR,
            url="https://example.com",
            error_message="Connection refused",
        )

        mock_scraper = AsyncMock()
        mock_scraper.fetch_batch = AsyncMock(return_value=[mock_result])
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=None)
        orchestrator.web_scraper = mock_scraper

        result = await orchestrator._fetch_with_http("Test Source", ["https://example.com"])

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_dict_on_success(self, orchestrator):
        from credentialing.scraper import ScraperStatus, ScraperResult

        mock_result = ScraperResult(
            status=ScraperStatus.SUCCESS,
            url="https://example.com",
            html="<html>data</html>",
            content="<html>data</html>",
            status_code=200,
        )

        mock_scraper = AsyncMock()
        mock_scraper.fetch_batch = AsyncMock(return_value=[mock_result])
        mock_scraper.__aenter__ = AsyncMock(return_value=mock_scraper)
        mock_scraper.__aexit__ = AsyncMock(return_value=None)
        orchestrator.web_scraper = mock_scraper

        result = await orchestrator._fetch_with_http(
            "CA Medical Board", ["https://example.com"]
        )

        assert result is not None
        assert result["source"] == "CA Medical Board"
        assert result["html_content"] == "<html>data</html>"