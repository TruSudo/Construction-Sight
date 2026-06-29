"""Parcel row preview models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.parcel_schema_models import ParcelFieldRoleMatch
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSourceFormat,
)


class ParcelRowPreviewStatus(StrEnum):
    """Readiness status for a parcel row preview."""

    READY_FOR_PARCEL_RECORD_MODEL = "ready_for_parcel_record_model"
    NEEDS_SCHEMA_MAPPING = "needs_schema_mapping"
    ROW_ISSUES = "row_issues"
    EMPTY_SOURCE = "empty_source"


class ParcelRowPreviewInput(BaseModel):
    """Preview request built from mapped schema fields and sample rows."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_format: ParcelSourceFormat
    field_role_matches: list[ParcelFieldRoleMatch] = Field(default_factory=list)
    rows: list[dict[str, str]] = Field(default_factory=list)
    geometry_support: ParcelGeometrySupport = ParcelGeometrySupport.UNKNOWN
    spatial_reference: str | None = None
    source_url: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("limitations must contain unique values")
        return values

    @field_validator("rows")
    @classmethod
    def reject_blank_row_keys(cls, values: list[dict[str, str]]) -> list[dict[str, str]]:
        """Reject blank row keys."""

        for row in values:
            for key in row:
                if not key.strip():
                    raise ValueError("parcel row preview keys cannot be blank")
        return values

    @model_validator(mode="after")
    def require_preview_basis(self) -> ParcelRowPreviewInput:
        """Require mapped fields or rows so preview has a basis."""

        if not self.field_role_matches and not self.rows:
            raise ValueError("parcel row preview requires mappings or rows")
        return self


class ParcelRowPreview(BaseModel):
    """Preview result for one candidate parcel row."""

    row_number: int = Field(ge=1)
    usable: bool
    normalized_apn: str | None = None
    normalized_address: str | None = None
    county: str | None = None
    source_record_id: str | None = None
    geometry_present: bool = False
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_row_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate row limitations."""

        if len(values) != len(set(values)):
            raise ValueError("row limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_skip_reason(self) -> ParcelRowPreview:
        """Require unusable rows to explain why they were skipped."""

        if not self.usable and not self.limitations:
            raise ValueError("unusable parcel rows require limitations")
        return self


class ParcelRowPreviewReport(BaseModel):
    """Safe preview report for candidate parcel rows."""

    preview_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_format: ParcelSourceFormat
    status: ParcelRowPreviewStatus
    row_count: int = Field(ge=0)
    usable_row_count: int = Field(ge=0)
    skipped_row_count: int = Field(ge=0)
    mapped_roles: list[ParcelFieldRole] = Field(default_factory=list)
    rows: list[ParcelRowPreview] = Field(default_factory=list)
    geometry_support: ParcelGeometrySupport = ParcelGeometrySupport.UNKNOWN
    spatial_reference: str | None = None
    limitations: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("mapped_roles")
    @classmethod
    def require_unique_mapped_roles(
        cls,
        values: list[ParcelFieldRole],
    ) -> list[ParcelFieldRole]:
        """Reject duplicate mapped roles."""

        if len(values) != len(set(values)):
            raise ValueError("mapped_roles must contain unique values")
        return values

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_count_consistency(self) -> ParcelRowPreviewReport:
        """Keep row counts and status honest."""

        if self.row_count != self.usable_row_count + self.skipped_row_count:
            raise ValueError("row counts must equal usable plus skipped rows")
        if self.row_count != len(self.rows):
            raise ValueError("row_count must equal number of row previews")
        if self.status == ParcelRowPreviewStatus.EMPTY_SOURCE and self.row_count != 0:
            raise ValueError("empty-source status requires zero rows")
        if self.status == ParcelRowPreviewStatus.ROW_ISSUES and self.skipped_row_count == 0:
            raise ValueError("row-issues status requires skipped rows")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe row preview payload."""

        return self.model_dump(mode="json")
