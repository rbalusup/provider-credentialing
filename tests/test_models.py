"""Tests for data models."""

import pytest
from datetime import datetime
from credentialing.models import (
    Provider,
    Credential,
    Sanction,
    CredentialStatus,
    SanctionStatus,
)


def test_provider_creation():
    """Test Provider model creation."""
    provider = Provider(
        first_name="John",
        last_name="Doe",
        npi="1234567890",
        state_code="CA",
        specialty="Internal Medicine",
    )

    assert provider.first_name == "John"
    assert provider.last_name == "Doe"
    assert provider.npi == "1234567890"
    assert provider.state_code == "CA"
    assert provider.specialty == "Internal Medicine"
    assert provider.created_at is not None


def test_provider_validation():
    """Test Provider model validation."""
    # Valid state code
    provider = Provider(
        first_name="Jane",
        last_name="Smith",
        state_code="NY",
    )
    assert provider.state_code == "NY"

    # Invalid state code (too long)
    with pytest.raises(ValueError):
        Provider(
            first_name="Jane",
            last_name="Smith",
            state_code="INVALID",
        )


def test_credential_creation():
    """Test Credential model creation."""
    credential = Credential(
        provider_id="provider_123",
        credential_type="license",
        issuing_authority="California Medical Board",
        credential_number="MD123456",
        status=CredentialStatus.ACTIVE,
        expiration_date="2026-12-31",
    )

    assert credential.provider_id == "provider_123"
    assert credential.credential_type == "license"
    assert credential.status == CredentialStatus.ACTIVE
    assert credential.created_at is not None


def test_sanction_creation():
    """Test Sanction model creation."""
    sanction = Sanction(
        provider_id="provider_123",
        sanction_type="license_suspension",
        status=SanctionStatus.SANCTIONED,
        source="OIG",
        description="Provider excluded from federal programs",
    )

    assert sanction.provider_id == "provider_123"
    assert sanction.sanction_type == "license_suspension"
    assert sanction.status == SanctionStatus.SANCTIONED
    assert sanction.source == "OIG"


def test_credential_status_enum():
    """Test CredentialStatus enum values."""
    statuses = [
        CredentialStatus.ACTIVE,
        CredentialStatus.INACTIVE,
        CredentialStatus.EXPIRED,
        CredentialStatus.SUSPENDED,
        CredentialStatus.REVOKED,
        CredentialStatus.UNKNOWN,
    ]

    assert len(statuses) == 6
    assert CredentialStatus.ACTIVE.value == "active"


def test_sanction_status_enum():
    """Test SanctionStatus enum values."""
    statuses = [
        SanctionStatus.CLEAR,
        SanctionStatus.SANCTIONED,
        SanctionStatus.UNDER_INVESTIGATION,
        SanctionStatus.UNKNOWN,
    ]

    assert len(statuses) == 4
    assert SanctionStatus.CLEAR.value == "clear"


def test_provider_json_serialization():
    """Test Provider JSON serialization."""
    provider = Provider(
        first_name="John",
        last_name="Doe",
        npi="1234567890",
        state_code="CA",
    )

    json_data = provider.model_dump_json()
    assert isinstance(json_data, str)
    assert "John" in json_data
    assert "Doe" in json_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])