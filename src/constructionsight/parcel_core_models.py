"""Canonical parcel core models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.site_resolution_service import normalize_address, normalize_apn


class ParcelGeometryKind(StrEnum):
    """Canonical geometry kinds supported by the parcel core layer."""

    POINT = "point"
    POLYGON = "polygon"
    MULTIPOLYGON = "multipolygon"
    UNKNOWN = "unknown"


class ParcelGeometry(BaseModel):
    """Provider-neutral parcel geometry summary."""

    geometry_kind: ParcelGeometryKind
    raw_geometry: str | None = None
    geometry_hash: str | None = None
    centroid_latitude: float | None = Field(default=None, ge=-90, le=90)
    centroid_longitude: float | None = Field(default=None, ge=-180, le=180)
    envelope_min_latitude: float | None = Field(default=None, ge=-90, le=90)
    envelope_min_longitude: float | None = Field(default=None, ge=-180, le=180)
    envelope_max_latitude: float | None = Field(default=None, ge=-90, le=90)
    envelope_max_longitude: float | None = Field(default=None, ge=-180, le=180)
    spatial_reference: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate geometry limitations."""

        if len(values) != len(set(values)):
            raise ValueError("geometry limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_geometry_signal(self) -> ParcelGeometry:
        """Require either raw geometry or centroid coordinates."""

        has_centroid = self.centroid_latitude is not None and self.centroid_longitude is not None
        if self.raw_geometry is None and not has_centroid:
            raise ValueError("parcel geometry requires raw geometry or centroid coordinates")
        return self


class ParcelCoreRecord(BaseModel):
    """Canonical provider-neutral parcel identity record."""

    parcel_record_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    source_record_id: str | None = None
    apn: str = Field(min_length=1)
    normalized_apn: str = Field(min_length=1)
    county: str = Field(min_length=1)
    state: str = Field(default="CA", min_length=2, max_length=2)
    address: str | None = None
    normalized_address: str | None = None
    jurisdiction: str | None = None
    zoning: str | None = None
    land_use: str | None = None
    acreage: float | None = Field(default=None, ge=0)
    geometry: ParcelGeometry | None = None
    source_updated_at: datetime | None = None
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate parcel limitations."""

        if len(values) != len(set(values)):
            raise ValueError("parcel limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_normalized_values(self) -> ParcelCoreRecord:
        """Require normalized values to match raw APN/address values."""

        if self.normalized_apn != normalize_apn(self.apn):
            raise ValueError("normalized_apn must match apn")
        if self.address is not None:
            expected_address = normalize_address(self.address)
            if self.normalized_address != expected_address:
                raise ValueError("normalized_address must match address")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe parcel payload."""

        return self.model_dump(mode="json")
