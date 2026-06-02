"""Core normalized data models for ConstructionSight.

These Pydantic models define the phase-1/phase-2 source registry contract. SQL
persistence models will be layered on top after the registry shape stabilizes.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class PlatformFamily(StrEnum):
    """Supported adapter platform families."""

    CEQANET = "ceqanet"
    CSLB = "cslb"
    ACCELA_ACA = "accela_aca"
    TYLER_ENERGOV = "tyler_energov"
    GRANICUS_LEGISTAR = "granicus_legistar"
    CIVICPLUS_PRIMEGOV = "civicplus_primegov"
    LASERFICHE = "laserfiche"
    CUSTOM_REPORT = "custom_report"
    UNKNOWN = "unknown"


class SourceType(StrEnum):
    """High-level source type."""

    STATE_REGISTRY = "state_registry"
    COUNTY_PORTAL = "county_portal"
    CITY_PORTAL = "city_portal"
    LEGISLATIVE_PACKET = "legislative_packet"
    DOCUMENT_REPOSITORY = "document_repository"
    CONTRACTOR_LICENSE = "contractor_license"
    GIS = "gis"
    OTHER = "other"


class VerificationStatus(StrEnum):
    """Verification state for a public source."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    PARTIAL = "partial"
    FAILED = "failed"
    BLOCKED = "blocked"


class ExtractionDifficulty(StrEnum):
    """Expected technical extraction difficulty."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    UNKNOWN = "unknown"


class RecordCategory(StrEnum):
    """Record categories the platform may discover from sources."""

    CEQA = "ceqa"
    PERMIT = "permit"
    PLANNING_CASE = "planning_case"
    AGENDA = "agenda"
    PARCEL = "parcel"
    CONTRACTOR_LICENSE = "contractor_license"
    INSPECTION = "inspection"
    DOCUMENT = "document"
    ZONING = "zoning"
    DEVELOPMENT_AGREEMENT = "development_agreement"
    TENTATIVE_MAP = "tentative_map"
    GRADING = "grading"
    BUILDING = "building"


class Jurisdiction(BaseModel):
    """Government jurisdiction covered by ConstructionSight."""

    name: str = Field(min_length=1)
    county: str = Field(min_length=1)
    state: str = Field(default="CA", min_length=2, max_length=2)
    jurisdiction_type: str = Field(description="city, county, state, district, or other")


class PublicSource(BaseModel):
    """Source registry record used to drive adapters and verification."""

    jurisdiction: Jurisdiction
    source_name: str = Field(min_length=1)
    source_type: SourceType
    platform_family: PlatformFamily
    public_url: HttpUrl
    record_categories: list[RecordCategory] = Field(default_factory=list)
    search_method: str | None = None
    extraction_difficulty: ExtractionDifficulty = ExtractionDifficulty.UNKNOWN
    update_frequency: str | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    provenance_notes: str | None = None
    last_checked_date: date | None = None

    @field_validator("record_categories")
    @classmethod
    def require_unique_categories(cls, value: list[RecordCategory]) -> list[RecordCategory]:
        """Reject duplicate category declarations."""

        if len(value) != len(set(value)):
            raise ValueError("record_categories must be unique")
        return value


class SourceVerificationResult(BaseModel):
    """Evidence captured when a source is verified."""

    source_name: str
    public_url: HttpUrl
    checked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    url_reachable: bool
    portal_type_detected: PlatformFamily = PlatformFamily.UNKNOWN
    public_search_available: bool | None = None
    login_required: bool | None = None
    permit_details_visible: bool | None = None
    agenda_packets_visible: bool | None = None
    pdfs_downloadable: bool | None = None
    contractor_owner_applicant_fields_visible: bool | None = None
    evidence_snapshot_text: str | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    notes: str | None = None
    raw_observations: dict[str, Any] = Field(default_factory=dict)
