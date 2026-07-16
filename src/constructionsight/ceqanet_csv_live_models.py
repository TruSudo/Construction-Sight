"""Exact-schema evidence models for one bounded live CEQAnet CSV request."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constructionsight.ceqanet_csv_models import (
    CeqanetCsvExportRequest,
    CeqanetCsvInspection,
    canonical_digest,
)

CSV_LIVE_EXECUTION_SCHEMA_VERSION: Final = "ceqanet_csv_live_execution.v1"
CSV_LIVE_VERIFICATION_SCHEMA_VERSION: Final = "ceqanet_csv_live_verification.v1"


class CeqanetCsvLiveExecution(BaseModel):
    """Tamper-evident response evidence from one explicitly authorized CSV GET."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_live_execution.v1"] = CSV_LIVE_EXECUTION_SCHEMA_VERSION
    request: CeqanetCsvExportRequest
    request_url: str = Field(min_length=1)
    final_url: str = Field(min_length=1)
    method: Literal["GET"] = "GET"
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    content_disposition: str | None = None
    observed_body_byte_length: int = Field(ge=0)
    retained_body_base64: str
    retained_body_byte_length: int = Field(ge=0)
    retained_body_complete: bool
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    network_executed: Literal[True] = True
    documents_downloaded: Literal[False] = False
    persistence_mutated: Literal[False] = False
    retry_count: Literal[0] = 0
    error: str | None = None
    inspection: CeqanetCsvInspection | None = None
    inspection_error: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_retention_consistency(self) -> CeqanetCsvLiveExecution:
        """Reject contradictory retained-body and inspection state."""

        retained = self.retained_body_bytes()
        if len(retained) != self.retained_body_byte_length:
            raise ValueError("retained_body_byte_length must equal decoded retained bytes")
        if self.retained_body_complete:
            if self.retained_body_byte_length != self.observed_body_byte_length:
                raise ValueError(
                    "complete retained body length must equal observed response length"
                )
        elif self.retained_body_byte_length != 0:
            raise ValueError("oversized responses must retain zero response bytes")
        if self.inspection is not None and not self.retained_body_complete:
            raise ValueError("CSV inspection requires a complete retained response body")
        if self.inspection is not None and self.inspection_error is not None:
            raise ValueError("inspection and inspection_error are mutually exclusive")
        return self

    def retained_body_bytes(self) -> bytes:
        """Decode the exact retained response bytes."""

        return base64.b64decode(self.retained_body_base64, validate=True)

    def evidence_payload(self) -> dict[str, Any]:
        """Return all retained evidence except timestamp and stored digest."""

        return self.model_dump(
            mode="json",
            exclude={"executed_at", "execution_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical digest of the complete retained evidence envelope."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Raise when any retained execution evidence changed."""

        if self.execution_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV live execution digest mismatch")


class CeqanetCsvLiveVerification(BaseModel):
    """Independent verification of one bounded live CSV execution artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_live_verification.v1"] = (
        CSV_LIVE_VERIFICATION_SCHEMA_VERSION
    )
    passed: bool
    finding_count: int = Field(ge=0)
    findings: list[str]
    request_url: str = Field(min_length=1)
    status_code: int | None = Field(default=None, ge=100, le=599)
    inspection_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_result_consistency(self) -> CeqanetCsvLiveVerification:
        """Require finding count and pass state to agree."""

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal findings length")
        if self.passed != (self.finding_count == 0):
            raise ValueError("passed must agree with finding_count")
        return self
