"""Exact-schema models for the governed CEQAnet CSV export boundary."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REQUEST_SCHEMA_VERSION = "ceqanet_csv_export_request.v1"
EXECUTION_SCHEMA_VERSION = "ceqanet_csv_export_execution.v1"
PARSE_SCHEMA_VERSION = "ceqanet_csv_parse_report.v1"
VERIFICATION_SCHEMA_VERSION = "ceqanet_csv_export_verification.v1"


class CeqanetCsvScope(StrEnum):
    """Official CEQAnet CSV export scope."""

    PROJECT = "project"
    DOCUMENT = "document"


class CeqanetCsvExportRequest(BaseModel):
    """One deterministic request for an official CEQAnet CSV export."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ceqanet_csv_export_request.v1"] = REQUEST_SCHEMA_VERSION
    scope: CeqanetCsvScope
    sch_number: str = Field(pattern=r"^\d{10}$")
    document_id: int | None = Field(default=None, ge=1)
    method: Literal["GET"] = "GET"
    documents_downloaded: Literal[False] = False
    persistence_authorized: Literal[False] = False

    @model_validator(mode="after")
    def require_scope_consistency(self) -> CeqanetCsvExportRequest:
        """Require document identity only for document-scoped exports."""

        if self.scope is CeqanetCsvScope.PROJECT and self.document_id is not None:
            raise ValueError("project CSV requests cannot include document_id")
        if self.scope is CeqanetCsvScope.DOCUMENT and self.document_id is None:
            raise ValueError("document CSV requests require document_id")
        return self


class CeqanetCsvRecord(BaseModel):
    """One lossless normalized row from an official CSV response."""

    model_config = ConfigDict(extra="forbid")

    row_number: int = Field(ge=2)
    values: dict[str, str]


class CeqanetCsvParseReport(BaseModel):
    """Strict offline parse result for one retained CSV body."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ceqanet_csv_parse_report.v1"] = PARSE_SCHEMA_VERSION
    source_url: str = Field(min_length=1)
    body_byte_length: int = Field(ge=0)
    body_sha256: str = Field(min_length=64, max_length=64)
    headers: list[str]
    row_count: int = Field(ge=0)
    records: list[CeqanetCsvRecord]
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_count_consistency(self) -> CeqanetCsvParseReport:
        """Require the reported count to match retained records."""

        if self.row_count != len(self.records):
            raise ValueError("CSV row_count must equal retained record count")
        return self


class CeqanetCsvExportExecution(BaseModel):
    """Tamper-evident retained evidence from one bounded CSV request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ceqanet_csv_export_execution.v1"] = EXECUTION_SCHEMA_VERSION
    request: CeqanetCsvExportRequest
    request_url: str = Field(min_length=1)
    final_url: str = Field(min_length=1)
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    content_disposition: str | None = None
    body_base64: str
    body_byte_length: int = Field(ge=0)
    body_sha256: str = Field(min_length=64, max_length=64)
    network_executed: bool
    documents_downloaded: Literal[False] = False
    persistence_mutated: Literal[False] = False
    error: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    execution_digest: str = Field(min_length=64, max_length=64)

    def body_bytes(self) -> bytes:
        """Decode the exact retained response bytes."""

        return base64.b64decode(self.body_base64, validate=True)

    def evidence_payload(self) -> dict[str, Any]:
        """Return digest-significant execution evidence."""

        return self.model_dump(
            mode="json",
            exclude={"executed_at", "execution_digest"},
        )

    def computed_digest(self) -> str:
        """Compute the canonical execution-evidence digest."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Reject altered execution evidence."""

        if self.execution_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV execution digest mismatch")


class CeqanetCsvExportVerification(BaseModel):
    """Verification result for one retained CEQAnet CSV execution."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ceqanet_csv_export_verification.v1"] = (
        VERIFICATION_SCHEMA_VERSION
    )
    passed: bool
    finding_count: int = Field(ge=0)
    findings: list[str]
    parsed_row_count: int | None = Field(default=None, ge=0)
    parsed_headers: list[str] = Field(default_factory=list)
    request_url: str = Field(min_length=1)
    execution_digest: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def require_result_consistency(self) -> CeqanetCsvExportVerification:
        """Require pass state and finding count to agree."""

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal findings length")
        if self.passed != (self.finding_count == 0):
            raise ValueError("passed must agree with finding_count")
        return self


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
