"""Exact-schema models for source-provided CEQAnet CSV exports."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CSV_REQUEST_SCHEMA_VERSION = "ceqanet_csv_export_request.v1"
CSV_INSPECTION_SCHEMA_VERSION = "ceqanet_csv_inspection.v1"


class CeqanetCsvExportKind(StrEnum):
    """Supported source-provided CEQAnet export scopes."""

    PROJECT = "project"
    DOCUMENT = "document"


class CeqanetCsvCanonicalRole(StrEnum):
    """Canonical roles recognized without discarding original CSV columns."""

    SCH_NUMBER = "sch_number"
    DOCUMENT_ID = "document_id"
    DOCUMENT_TYPE = "document_type"
    LEAD_AGENCY = "lead_agency"
    RECEIVED_DATE = "received_date"
    TITLE = "title"
    COUNTY = "county"
    LOCATION = "location"
    DESCRIPTION = "description"
    CONTACT_NAME = "contact_name"
    CONTACT_EMAIL = "contact_email"
    CONTACT_PHONE = "contact_phone"
    PARCEL_NUMBER = "parcel_number"


class CeqanetCsvExportRequest(BaseModel):
    """One exact official CEQAnet CSV export request identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_export_request.v1"] = CSV_REQUEST_SCHEMA_VERSION
    export_kind: CeqanetCsvExportKind
    sch_number: str = Field(pattern=r"^\d{10}$")
    document_id: int | None = Field(default=None, ge=1)
    source_url: str = Field(min_length=1)
    network_authorized: Literal[False] = False
    persistence_authorized: Literal[False] = False

    @model_validator(mode="after")
    def require_kind_identity_consistency(self) -> CeqanetCsvExportRequest:
        """Require document identity only for document-scoped exports."""

        if self.export_kind is CeqanetCsvExportKind.PROJECT and self.document_id is not None:
            raise ValueError("project CSV exports cannot contain document_id")
        if self.export_kind is CeqanetCsvExportKind.DOCUMENT and self.document_id is None:
            raise ValueError("document CSV exports require document_id")
        return self


class CeqanetCsvColumn(BaseModel):
    """One preserved CSV column and optional canonical role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=0)
    original_name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    canonical_role: CeqanetCsvCanonicalRole | None = None


class CeqanetCsvInspection(BaseModel):
    """Digest-bound offline inspection of one CEQAnet CSV body."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_inspection.v1"] = CSV_INSPECTION_SCHEMA_VERSION
    request: CeqanetCsvExportRequest
    content_type: str | None = None
    encoding: Literal["utf-8-sig"] = "utf-8-sig"
    delimiter: Literal[","] = ","
    byte_length: int = Field(ge=1)
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    column_count: int = Field(ge=1)
    columns: list[CeqanetCsvColumn] = Field(min_length=1)
    row_count: int = Field(ge=1)
    retained_row_count: int = Field(ge=0)
    rows: list[dict[str, str]] = Field(default_factory=list)
    rows_truncated: bool
    unknown_columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    network_executed: Literal[False] = False
    persistence_authorized: Literal[False] = False
    inspection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_internal_consistency(self) -> CeqanetCsvInspection:
        """Reject count, column, and truncation contradictions."""

        if self.column_count != len(self.columns):
            raise ValueError("column_count must equal the number of columns")
        if self.retained_row_count != len(self.rows):
            raise ValueError("retained_row_count must equal the number of retained rows")
        if self.retained_row_count > self.row_count:
            raise ValueError("retained_row_count cannot exceed row_count")
        if self.rows_truncated != (self.retained_row_count < self.row_count):
            raise ValueError("rows_truncated must agree with retained and total row counts")
        normalized_names = [column.normalized_name for column in self.columns]
        if len(normalized_names) != len(set(normalized_names)):
            raise ValueError("normalized CSV column names must be unique")
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return all inspection evidence except the stored digest."""

        return self.model_dump(mode="json", exclude={"inspection_digest"})

    def computed_digest(self) -> str:
        """Return the canonical digest for all retained inspection evidence."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Raise when retained inspection evidence differs from its digest."""

        if self.inspection_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV inspection digest mismatch")


def canonical_digest(payload: Any) -> str:
    """Return SHA-256 over canonical JSON content."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
