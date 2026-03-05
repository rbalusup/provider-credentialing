"""Data models for provider credentialing."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CredentialStatus(str, Enum):
    """Provider credential status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    UNKNOWN = "unknown"


class SanctionStatus(str, Enum):
    """Provider sanction status."""
    CLEAR = "clear"
    SANCTIONED = "sanctioned"
    UNDER_INVESTIGATION = "under_investigation"
    UNKNOWN = "unknown"


class ExtractionStatus(str, Enum):
    """Data extraction status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class Provider(BaseModel):
    """Provider information model."""
    id: Optional[str] = None
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    npi: Optional[str] = None
    license_number: Optional[str] = None
    state_code: str = Field(..., min_length=2, max_length=2)
    specialty: Optional[str] = None
    provider_type: Optional[str] = None
    date_of_birth: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "npi": "1234567890",
                "license_number": "MD123456",
                "state_code": "CA",
                "specialty": "Internal Medicine",
            }
        }


class Credential(BaseModel):
    """Provider credential information."""
    id: Optional[str] = None
    provider_id: str
    credential_type: str  # e.g., "license", "board_certification", "DEA"
    issuing_authority: str
    credential_number: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    status: CredentialStatus = CredentialStatus.UNKNOWN
    source_url: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "provider_id": "provider_123",
                "credential_type": "license",
                "issuing_authority": "California Medical Board",
                "credential_number": "MD123456",
                "status": "active",
            }
        }


class Sanction(BaseModel):
    """Provider sanction record."""
    id: Optional[str] = None
    provider_id: str
    sanction_type: str  # e.g., "license_suspension", "exclusion", "malpractice"
    description: Optional[str] = None
    sanction_date: Optional[str] = None
    status: SanctionStatus = SanctionStatus.UNKNOWN
    source: str  # e.g., "OFAC", "OIG", "State Medical Board"
    source_url: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "provider_id": "provider_123",
                "sanction_type": "exclusion",
                "description": "Excluded from federal healthcare programs",
                "status": "clear",
                "source": "OIG",
            }
        }


class ExtractionResult(BaseModel):
    """Result of data extraction from web source."""
    id: Optional[str] = None
    provider_id: str
    source_name: str  # e.g., "CA Medical Board", "NPDB"
    source_url: str
    status: ExtractionStatus = ExtractionStatus.PENDING
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    raw_html: Optional[str] = None
    error_message: Optional[str] = None
    extraction_time_ms: Optional[int] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CredentialingTask(BaseModel):
    """Credentialing task for processing."""
    id: Optional[str] = None
    provider: Provider
    sources: List[str] = Field(default_factory=list)  # e.g., ["CA Medical Board", "NPDB", "OIG"]
    status: ExtractionStatus = ExtractionStatus.PENDING
    extraction_results: List[ExtractionResult] = Field(default_factory=list)
    credentials: List[Credential] = Field(default_factory=list)
    sanctions: List[Sanction] = Field(default_factory=list)
    normalized_data: Optional[Dict[str, Any]] = None
    errors: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ClaudeExtractionPrompt(BaseModel):
    """Prompt configuration for Claude-based extraction."""
    field_name: str
    description: str
    expected_format: str
    is_required: bool = False


class ClaudeExtractionRequest(BaseModel):
    """Request for Claude-based data extraction."""
    source_content: str  # HTML or text content from web source
    extraction_fields: List[ClaudeExtractionPrompt]
    context: Optional[Dict[str, Any]] = None


class ClaudeExtractionResponse(BaseModel):
    """Response from Claude-based extraction."""
    extracted_fields: Dict[str, Any]
    confidence_scores: Dict[str, float]
    raw_response: str
    processing_time_ms: int