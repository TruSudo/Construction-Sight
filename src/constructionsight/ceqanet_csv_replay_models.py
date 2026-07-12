"""Derived evidence models for offline CEQAnet CSV encoding replay."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constructionsight.ceqanet_csv_models import CeqanetCsvInspection, canonical_digest

CSV_REPLAY_SCHEMA_VERSION: Final = "ceqanet_csv_encoding_replay.v1"
CSV_REPLAY_VERIFICATION_SCHEMA_VERSION: Final = "ceqanet_csv_encoding_replay_verification.v1"


class CeqanetCsvEncodingReplay(BaseModel):
    """One digest-bound offline replay derived from retained live response bytes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_encoding_replay.v1"] = CSV_REPLAY_SCHEMA_VERSION
    source_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_body_byte_length: int = Field(ge=1)
    source_request_url: str = Field(min_length=1)
    source_status_code: int = Field(ge=100, le=599)
    inspection: CeqanetCsvInspection
    network_executed: Literal[False] = False
    persistence_mutated: Literal[False] = False
    replayed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_source_inspection_consistency(self) -> CeqanetCsvEncodingReplay:
        """Require replay metadata to agree with the derived inspection."""

        if self.source_body_sha256 != self.inspection.body_sha256:
            raise ValueError("replay source body SHA-256 must equal inspection body SHA-256")
        if self.source_body_byte_length != self.inspection.byte_length:
            raise ValueError("replay source byte length must equal inspection byte length")
        if self.source_request_url != self.inspection.request.source_url:
            raise ValueError("replay source URL must equal inspection request URL")
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return all replay evidence except timestamp and stored digest."""

        return self.model_dump(
            mode="json",
            exclude={"replayed_at", "replay_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical digest for all retained replay evidence."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Raise when retained replay evidence differs from its digest."""

        if self.replay_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV encoding replay digest mismatch")


class CeqanetCsvEncodingReplayVerification(BaseModel):
    """Independent verification of one derived encoding replay artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_encoding_replay_verification.v1"] = (
        CSV_REPLAY_VERIFICATION_SCHEMA_VERSION
    )
    passed: bool
    finding_count: int = Field(ge=0)
    findings: list[str]
    source_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inspection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_result_consistency(self) -> CeqanetCsvEncodingReplayVerification:
        """Require finding count and pass state to agree."""

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal findings length")
        if self.passed != (self.finding_count == 0):
            raise ValueError("passed must agree with finding_count")
        return self
