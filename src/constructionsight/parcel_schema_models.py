"""Parcel source schema preview models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSourceFormat,
)


class ParcelSchemaPreviewStatus(StrEnum):
    """Readiness status for a schema preview."""

    READY_FOR_IMPORT_PREVIEW = "ready_for_import_preview"
    NEEDS_MAPPING = "needs_mapping"
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    UNSUPPORTED = "unsupported"


class ParcelObservedFieldType(StrEnum):
    """Provider-neutral observed source field type."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    GEOMETRY = "geometry"
    OBJECT = "object"
    ARRAY = "array"
    UNKNOWN = "unknown"


class ParcelSchemaField(BaseModel):
    """One observed field from a parcel source schema or sample file."""

    source_field: str = Field(min_length=1)
    observed_type: ParcelObservedFieldType = ParcelObservedFieldType.UNKNOWN
    description: str | None = None
    nullable: bool | None = None
    sample_values: list[str] = Field(default_factory=list)

    @field_validator("source_field")
    @classmethod
    def reject_blank_source_field(cls, value: str) -> str:
        """Reject blank source field names."""

        if not value.strip():
            raise ValueError("source_field cannot be blank")
        return value

    @field_validator("sample_values")
    @classmethod
    def require_unique_sample_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate sample values."""

        if len(values) != len(set(values)):
            raise ValueError("sample_values must contain unique values")
        return values


class ParcelFieldRoleMatch(BaseModel):
    """Mapping from an observed field to a canonical parcel role."""

    source_field: str = Field(min_length=1)
    field_role: ParcelFieldRole
    match_reason: str = Field(min_length=1)
    confidence_score: int = Field(ge=0, le=100)
    required_role: bool = False


class ParcelSchemaPreviewInput(BaseModel):
    """Schema preview request built from source metadata or a user-provided file."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_format: ParcelSourceFormat
    observed_fields: list[ParcelSchemaField] = Field(default_factory=list)
    geometry_support: ParcelGeometrySupport = ParcelGeometrySupport.UNKNOWN
    spatial_reference: str | None = None
    sample_record_count: int | None = Field(default=None, ge=0)
    source_url: str | None = None
    limitations: list[str] = Field(default_factory=list)

    @field_validator("observed_fields")
    @classmethod
    def require_unique_observed_fields(
        cls,
        values: list[ParcelSchemaField],
    ) -> list[ParcelSchemaField]:
        """Reject duplicate observed field names."""

        field_names = [field.source_field.lower() for field in values]
        if len(field_names) != len(set(field_names)):
            raise ValueError("observed_fields cannot repeat source field names")
        return values

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("limitations must contain unique values")
        return values

    @model_validator(mode="after")
    def require_schema_signal(self) -> ParcelSchemaPreviewInput:
        """Require at least one field or geometry signal."""

        if not self.observed_fields and self.geometry_support == ParcelGeometrySupport.UNKNOWN:
            raise ValueError("schema preview requires observed fields or known geometry support")
        return self


class ParcelSchemaPreviewReport(BaseModel):
    """Readiness report for one parcel source schema preview."""

    preview_id: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_format: ParcelSourceFormat
    status: ParcelSchemaPreviewStatus
    observed_field_count: int = Field(ge=0)
    mapped_fields: list[ParcelFieldRoleMatch] = Field(default_factory=list)
    unmapped_fields: list[str] = Field(default_factory=list)
    missing_required_roles: list[ParcelFieldRole] = Field(default_factory=list)
    geometry_support: ParcelGeometrySupport = ParcelGeometrySupport.UNKNOWN
    spatial_reference: str | None = None
    sample_record_count: int | None = Field(default=None, ge=0)
    limitations: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("unmapped_fields", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate text rows."""

        if len(values) != len(set(values)):
            raise ValueError("preview text lists must contain unique values")
        return values

    @field_validator("missing_required_roles")
    @classmethod
    def require_unique_missing_roles(
        cls,
        values: list[ParcelFieldRole],
    ) -> list[ParcelFieldRole]:
        """Reject duplicate missing roles."""

        if len(values) != len(set(values)):
            raise ValueError("missing_required_roles must contain unique values")
        return values

    @model_validator(mode="after")
    def require_status_consistency(self) -> ParcelSchemaPreviewReport:
        """Keep preview status consistent with missing roles and mapping state."""

        if (
            self.status == ParcelSchemaPreviewStatus.READY_FOR_IMPORT_PREVIEW
            and self.missing_required_roles
        ):
            raise ValueError("ready schema previews cannot have missing required roles")
        if (
            self.status == ParcelSchemaPreviewStatus.MISSING_REQUIRED_FIELDS
            and not self.missing_required_roles
        ):
            raise ValueError("missing-required status requires missing roles")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe preview payload."""

        return self.model_dump(mode="json")
