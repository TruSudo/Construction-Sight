"""External intelligence capability models for lawful feature parity planning."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ReferencePlatform(StrEnum):
    """Reference platforms used for lawful capability analysis."""

    SHOVELS = "shovels"
    REGRID = "regrid"
    CONSTRUCTIONSIGHT = "constructionsight"


class CapabilityDomain(StrEnum):
    """Capability domains ConstructionSight can implement or outperform."""

    PERMIT_DATA = "permit_data"
    CONTRACTOR_INTELLIGENCE = "contractor_intelligence"
    GOVERNMENT_DECISIONS = "government_decisions"
    PARCEL_DATA = "parcel_data"
    PARCEL_GEOMETRY = "parcel_geometry"
    PROPERTY_ENRICHMENT = "property_enrichment"
    ADDRESS_RESOLUTION = "address_resolution"
    GEO_SEARCH = "geo_search"
    COVERAGE_METRICS = "coverage_metrics"
    API_ACCESS = "api_access"
    CLI_ACCESS = "cli_access"
    GIS_ACCESS = "gis_access"
    DATA_WAREHOUSE_FEED = "data_warehouse_feed"
    BULK_DELIVERY = "bulk_delivery"
    AUDIENCE_TARGETING = "audience_targeting"
    AI_INSIGHTS = "ai_insights"
    UPDATE_MONITORING = "update_monitoring"
    DERIVED_METRICS = "derived_metrics"
    WORKFLOW_INTEGRATION = "workflow_integration"


class LawfulAccessBoundary(StrEnum):
    """Lawful acquisition boundary for a capability target."""

    PUBLIC_DOCS_ONLY = "public_docs_only"
    OPEN_PUBLIC_RECORDS = "open_public_records"
    LAWFUL_API_OR_LICENSE = "lawful_api_or_license"
    USER_PROVIDED_LICENSE = "user_provided_license"
    UNSUPPORTED = "unsupported"


class CapabilityEvidenceKind(StrEnum):
    """Kind of source supporting the capability claim."""

    PUBLIC_WEBSITE = "public_website"
    PUBLIC_DOCUMENTATION = "public_documentation"
    USER_RESEARCH = "user_research"
    PRODUCT_DOCTRINE = "product_doctrine"


class ImplementationStatus(StrEnum):
    """ConstructionSight implementation status for a capability target."""

    NOT_STARTED = "not_started"
    DESIGNED = "designed"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    OUTPERFORM_TARGET = "outperform_target"
    BLOCKED_BY_LICENSE = "blocked_by_license"


class DeliveryMode(StrEnum):
    """How a capability is exposed or delivered."""

    WEB_APP = "web_app"
    API = "api"
    CLI = "cli"
    GIS = "gis"
    DATA_WAREHOUSE = "data_warehouse"
    BULK_FILE = "bulk_file"
    TILE_SERVICE = "tile_service"
    FEATURE_SERVICE = "feature_service"
    INTERNAL_ENGINE = "internal_engine"


class CapabilityReference(BaseModel):
    """Public or user-provided evidence for one capability claim."""

    evidence_kind: CapabilityEvidenceKind
    source_name: str = Field(min_length=1)
    source_url: str | None = None
    claim: str = Field(min_length=1)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExternalCapability(BaseModel):
    """One competitor or reference capability mapped into ConstructionSight."""

    capability_key: str = Field(min_length=1)
    platform: ReferencePlatform
    domain: CapabilityDomain
    label: str = Field(min_length=1)
    description: str = Field(min_length=1)
    delivery_modes: list[DeliveryMode] = Field(default_factory=list)
    update_frequency: str | None = None
    lawful_boundary: LawfulAccessBoundary
    references: list[CapabilityReference] = Field(default_factory=list)
    construction_sight_target: str = Field(min_length=1)
    implementation_status: ImplementationStatus = ImplementationStatus.DESIGNED
    improvement_strategy: str = Field(min_length=1)
    normalized_output_contracts: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("delivery_modes", "normalized_output_contracts", "notes")
    @classmethod
    def require_unique_values(cls, values: list[Any]) -> list[Any]:
        """Keep list fields deterministic."""

        if len(values) != len(set(values)):
            raise ValueError("capability list fields must contain unique values")
        return values

    @model_validator(mode="after")
    def require_reference_or_product_doctrine(self) -> ExternalCapability:
        """Require every external claim to be grounded."""

        if self.platform != ReferencePlatform.CONSTRUCTIONSIGHT and not self.references:
            raise ValueError("external capabilities require at least one reference")
        if self.implementation_status == ImplementationStatus.BLOCKED_BY_LICENSE and (
            self.lawful_boundary
            not in {
                LawfulAccessBoundary.LAWFUL_API_OR_LICENSE,
                LawfulAccessBoundary.USER_PROVIDED_LICENSE,
            }
        ):
            raise ValueError("license-blocked capabilities must declare a license boundary")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe capability payload."""

        return self.model_dump(mode="json")


class CapabilityGap(BaseModel):
    """ConstructionSight implementation gap for one reference capability."""

    capability_key: str = Field(min_length=1)
    platform: ReferencePlatform
    domain: CapabilityDomain
    label: str = Field(min_length=1)
    status: ImplementationStatus
    lawful_boundary: LawfulAccessBoundary
    target: str = Field(min_length=1)
    improvement_strategy: str = Field(min_length=1)
    priority: int = Field(ge=0, le=100)


class CapabilityGapReport(BaseModel):
    """Summary report for external capability parity and advantage planning."""

    report_id: str = Field(min_length=1)
    capabilities_reviewed: int = Field(ge=0)
    platforms: list[ReferencePlatform] = Field(default_factory=list)
    gaps: list[CapabilityGap] = Field(default_factory=list)
    outperform_targets: list[CapabilityGap] = Field(default_factory=list)
    blocked_by_license: list[CapabilityGap] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("platforms")
    @classmethod
    def require_unique_platforms(
        cls,
        values: list[ReferencePlatform],
    ) -> list[ReferencePlatform]:
        """Reject duplicate platforms."""

        if len(values) != len(set(values)):
            raise ValueError("platforms must contain unique values")
        return values

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe report payload."""

        return self.model_dump(mode="json")
