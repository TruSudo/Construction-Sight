"""Parcel source registry models for ConstructionSight."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class ParcelProviderKind(StrEnum):
    """Kinds of parcel providers ConstructionSight can support."""

    COUNTY_GIS = "county_gis"
    CITY_GIS = "city_gis"
    ASSESSOR_EXPORT = "assessor_export"
    LICENSED_PROVIDER = "licensed_provider"
    USER_PROVIDED_FILE = "user_provided_file"
    OPEN_DATA_PORTAL = "open_data_portal"
    UNKNOWN = "unknown"


class ParcelAccessBoundary(StrEnum):
    """Lawful access boundary for a parcel source."""

    OPEN_PUBLIC_DATA = "open_public_data"
    PUBLIC_METADATA_ONLY = "public_metadata_only"
    LAWFUL_API_OR_LICENSE = "lawful_api_or_license"
    USER_PROVIDED_FILE = "user_provided_file"
    UNSUPPORTED = "unsupported"


class ParcelCoverageStatus(StrEnum):
    """Operational status of a parcel source target."""

    TARGET = "target"
    DESIGNED = "designed"
    READY_FOR_PREVIEW = "ready_for_preview"
    READY_FOR_IMPORT = "ready_for_import"
    BLOCKED_BY_LICENSE = "blocked_by_license"
    UNSUPPORTED = "unsupported"


class ParcelGeometrySupport(StrEnum):
    """Geometry support level advertised or expected from a parcel source."""

    NONE = "none"
    CENTROID = "centroid"
    POLYGON = "polygon"
    MULTIPOLYGON = "multipolygon"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ParcelFieldRole(StrEnum):
    """Canonical roles for parcel source fields."""

    APN = "apn"
    ADDRESS = "address"
    OWNER = "owner"
    SITUS_CITY = "situs_city"
    COUNTY = "county"
    STATE = "state"
    JURISDICTION = "jurisdiction"
    ZONING = "zoning"
    LAND_USE = "land_use"
    ACREAGE = "acreage"
    CENTROID_LATITUDE = "centroid_latitude"
    CENTROID_LONGITUDE = "centroid_longitude"
    GEOMETRY = "geometry"
    SOURCE_RECORD_ID = "source_record_id"
    UPDATED_AT = "updated_at"
    UNKNOWN = "unknown"


class ParcelSourceFormat(StrEnum):
    """Supported source delivery formats."""

    ARCGIS_FEATURE_SERVICE = "arcgis_feature_service"
    GEOJSON = "geojson"
    SHAPEFILE = "shapefile"
    CSV = "csv"
    PARQUET = "parquet"
    FILE_GEODATABASE = "file_geodatabase"
    API_JSON = "api_json"
    UNKNOWN = "unknown"


class ParcelFieldMapping(BaseModel):
    """Map one source field name to a canonical parcel field role."""

    source_field: str = Field(min_length=1)
    field_role: ParcelFieldRole
    required: bool = False
    notes: str | None = None

    @field_validator("source_field")
    @classmethod
    def reject_blank_source_field(cls, value: str) -> str:
        """Reject blank source field names."""

        if not value.strip():
            raise ValueError("source_field cannot be blank")
        return value


class ParcelSourceCoverage(BaseModel):
    """Geographic and schema coverage metadata for one parcel source."""

    county: str = Field(min_length=1)
    state: str = Field(default="CA", min_length=2, max_length=2)
    jurisdictions: list[str] = Field(default_factory=list)
    geometry_support: ParcelGeometrySupport = ParcelGeometrySupport.UNKNOWN
    expected_record_count: int | None = Field(default=None, ge=0)
    coverage_notes: list[str] = Field(default_factory=list)

    @field_validator("jurisdictions", "coverage_notes")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Keep coverage lists deterministic."""

        if len(values) != len(set(values)):
            raise ValueError("coverage lists must contain unique values")
        return values


class ParcelSource(BaseModel):
    """One provider-neutral parcel source target."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    provider_kind: ParcelProviderKind
    access_boundary: ParcelAccessBoundary
    coverage_status: ParcelCoverageStatus
    source_format: ParcelSourceFormat
    coverage: ParcelSourceCoverage
    source_url: str | None = None
    documentation_url: str | None = None
    update_frequency: str | None = None
    field_mappings: list[ParcelFieldMapping] = Field(default_factory=list)
    priority: int = Field(default=50, ge=0, le=100)
    limitations: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("field_mappings")
    @classmethod
    def require_unique_field_roles(cls, values: list[ParcelFieldMapping]) -> list[ParcelFieldMapping]:
        """Reject duplicate source fields and duplicate canonical roles."""

        source_fields = [mapping.source_field.lower() for mapping in values]
        roles = [mapping.field_role for mapping in values if mapping.field_role != ParcelFieldRole.UNKNOWN]
        if len(source_fields) != len(set(source_fields)):
            raise ValueError("field_mappings cannot repeat source fields")
        if len(roles) != len(set(roles)):
            raise ValueError("field_mappings cannot repeat canonical field roles")
        return values

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_license_boundary_consistency(self) -> ParcelSource:
        """Keep licensed and blocked source records honest."""

        if self.coverage_status == ParcelCoverageStatus.BLOCKED_BY_LICENSE and (
            self.access_boundary != ParcelAccessBoundary.LAWFUL_API_OR_LICENSE
        ):
            raise ValueError("license-blocked parcel sources must use license boundary")
        if self.access_boundary == ParcelAccessBoundary.OPEN_PUBLIC_DATA and not self.source_url:
            raise ValueError("open public parcel sources require a source_url")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe source payload."""

        return self.model_dump(mode="json")


class ParcelSourceGap(BaseModel):
    """Implementation gap row for a parcel source."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    county: str = Field(min_length=1)
    provider_kind: ParcelProviderKind
    access_boundary: ParcelAccessBoundary
    coverage_status: ParcelCoverageStatus
    priority: int = Field(ge=0, le=100)
    next_action: str = Field(min_length=1)


class ParcelSourceRegistryReport(BaseModel):
    """Summary report for parcel source readiness."""

    report_id: str = Field(min_length=1)
    sources_reviewed: int = Field(ge=0)
    counties: list[str] = Field(default_factory=list)
    ready_sources: list[ParcelSourceGap] = Field(default_factory=list)
    target_sources: list[ParcelSourceGap] = Field(default_factory=list)
    blocked_sources: list[ParcelSourceGap] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("counties")
    @classmethod
    def require_unique_counties(cls, values: list[str]) -> list[str]:
        """Reject duplicate county names."""

        if len(values) != len(set(values)):
            raise ValueError("counties must contain unique values")
        return values

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe report payload."""

        return self.model_dump(mode="json")
