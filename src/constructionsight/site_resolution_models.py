"""Parcel and site-resolution models for ConstructionSight."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.domain_types import ConfidenceBand, confidence_band


class SiteIdentifierKind(StrEnum):
    """Kinds of identifiers that can anchor a physical site."""

    APN = "apn"
    ADDRESS = "address"
    COORDINATE = "coordinate"
    GEOMETRY = "geometry"
    JURISDICTION = "jurisdiction"
    COUNTY = "county"
    SOURCE_RECORD = "source_record"


class GeometryHintKind(StrEnum):
    """Supported geometry hint families before full GIS storage exists."""

    POINT = "point"
    CENTROID = "centroid"
    POLYGON = "polygon"
    BOUNDING_BOX = "bounding_box"
    UNKNOWN = "unknown"


class SiteResolutionStatus(StrEnum):
    """Result status for source-neutral site resolution."""

    RESOLVED = "resolved"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    CONFLICTING = "conflicting"
    UNRESOLVED = "unresolved"


class SiteMatchStrength(StrEnum):
    """Human-readable site match strength."""

    NONE = "none"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXACT = "exact"


class SiteIdentifier(BaseModel):
    """One normalized identifier that may help resolve a site."""

    identifier_kind: SiteIdentifierKind
    value: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    evidence_id: str | None = None
    fact_id: str | None = None
    source_field: str | None = None
    confidence_score: int = Field(default=50, ge=0, le=100)

    @field_validator("value", "normalized_value")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        """Reject blank identifier strings."""

        if not value.strip():
            raise ValueError("site identifier values cannot be blank")
        return value


class GeometryHint(BaseModel):
    """Lightweight geometry hint before provider-specific geometry ingestion."""

    geometry_kind: GeometryHintKind
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    raw_geometry: str | None = None
    source_name: str = Field(min_length=1)
    evidence_id: str | None = None
    confidence_score: int = Field(default=50, ge=0, le=100)

    @model_validator(mode="after")
    def require_point_or_raw_geometry(self) -> GeometryHint:
        """Require coordinates for point-like hints or raw geometry otherwise."""

        if self.geometry_kind in {GeometryHintKind.POINT, GeometryHintKind.CENTROID} and (
            self.latitude is None or self.longitude is None
        ):
            raise ValueError("point and centroid geometry hints require latitude and longitude")
        if self.geometry_kind in {GeometryHintKind.POLYGON, GeometryHintKind.BOUNDING_BOX} and (
            not self.raw_geometry
        ):
            raise ValueError("polygon and bounding-box geometry hints require raw_geometry")
        return self


class SiteResolutionInput(BaseModel):
    """Source-neutral site-resolution request."""

    source_name: str = Field(min_length=1)
    evidence_id: str | None = None
    identifiers: list[SiteIdentifier] = Field(default_factory=list)
    geometry_hints: list[GeometryHint] = Field(default_factory=list)
    source_hints: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("identifiers")
    @classmethod
    def require_unique_identifiers(cls, values: list[SiteIdentifier]) -> list[SiteIdentifier]:
        """Reject duplicate identifier kind/value pairs."""

        keys = [(item.identifier_kind, item.normalized_value) for item in values]
        if len(keys) != len(set(keys)):
            raise ValueError("site identifiers must be unique by kind and normalized value")
        return values

    @field_validator("source_hints")
    @classmethod
    def reject_blank_source_hints(cls, values: dict[str, str]) -> dict[str, str]:
        """Reject blank source-hint keys or values."""

        for key, value in values.items():
            if not key.strip() or not value.strip():
                raise ValueError("source_hints cannot contain blank keys or values")
        return values

    @model_validator(mode="after")
    def require_some_site_signal(self) -> SiteResolutionInput:
        """Require at least one site signal."""

        if not (self.identifiers or self.geometry_hints or self.source_hints):
            raise ValueError("site resolution input requires an identifier, geometry hint, or source hint")
        return self


class SiteResolutionCandidate(BaseModel):
    """One candidate site anchor produced by source-neutral resolution."""

    site_key: str = Field(min_length=1)
    match_strength: SiteMatchStrength
    confidence_score: int = Field(ge=0, le=100)
    confidence_band: ConfidenceBand
    county: str | None = None
    state: str = Field(default="CA", min_length=2, max_length=2)
    jurisdiction: str | None = None
    apn: str | None = None
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    supporting_identifiers: list[SiteIdentifier] = Field(default_factory=list)
    geometry_hints: list[GeometryHint] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text(cls, values: list[str]) -> list[str]:
        """Keep narrative fields deterministic."""

        if len(values) != len(set(values)):
            raise ValueError("candidate narrative fields must contain unique values")
        return values

    @model_validator(mode="after")
    def require_band_matches_score(self) -> SiteResolutionCandidate:
        """Require the confidence band to match the numeric score."""

        if self.confidence_band != confidence_band(self.confidence_score):
            raise ValueError("confidence_band must match confidence_score")
        return self


class SiteResolutionResult(BaseModel):
    """Resolution result for one source-neutral site request."""

    resolution_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    evidence_id: str | None = None
    status: SiteResolutionStatus
    primary_site_key: str | None = None
    candidates: list[SiteResolutionCandidate] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("conflicts", "limitations")
    @classmethod
    def require_unique_result_text(cls, values: list[str]) -> list[str]:
        """Reject duplicate result narrative entries."""

        if len(values) != len(set(values)):
            raise ValueError("result narrative fields must contain unique values")
        return values

    @model_validator(mode="after")
    def require_status_payload_consistency(self) -> SiteResolutionResult:
        """Keep status honest relative to candidate/conflict payload."""

        if self.status == SiteResolutionStatus.UNRESOLVED and self.candidates:
            raise ValueError("unresolved results cannot include candidates")
        if self.status != SiteResolutionStatus.UNRESOLVED and not self.candidates:
            raise ValueError("resolved or partial results require candidates")
        if self.status == SiteResolutionStatus.CONFLICTING and not self.conflicts:
            raise ValueError("conflicting results require conflict descriptions")
        if self.primary_site_key is not None and self.primary_site_key not in {
            candidate.site_key for candidate in self.candidates
        }:
            raise ValueError("primary_site_key must reference a candidate site_key")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe result payload."""

        return self.model_dump(mode="json")
