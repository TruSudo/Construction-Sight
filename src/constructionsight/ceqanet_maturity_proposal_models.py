"""Exact-schema models for a report-only CEQAnet source-maturity proposal."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.ceqanet_csv_models import canonical_digest

MATURITY_PROPOSAL_SCHEMA_VERSION: Final = "ceqanet_source_maturity_proposal.v1"
MATURITY_VERIFICATION_SCHEMA_VERSION: Final = (
    "ceqanet_source_maturity_proposal_verification.v1"
)


class CeqanetMaturityDecision(StrEnum):
    """Conservative outcome supported by the current retained evidence."""

    KEEP_PARTIAL = "keep_partial"


class CeqanetSourceMaturityProposal(BaseModel):
    """Digest-bound proposal that cannot itself promote or authorize a source."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_source_maturity_proposal.v1"] = (
        MATURITY_PROPOSAL_SCHEMA_VERSION
    )
    source_name: str = Field(min_length=1)
    registry_status: Literal["partial"] = "partial"
    source_registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    live_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    inspection_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_verification_passed: Literal[True] = True
    observed_status_code: Literal[200] = 200
    observed_row_count: int = Field(ge=1)
    observed_encoding: Literal["windows-1252"] = "windows-1252"
    network_executed: Literal[False] = False
    persistence_mutated: Literal[False] = False
    registry_mutation_authorized: Literal[False] = False
    recurring_execution_authorized: Literal[False] = False
    decision: CeqanetMaturityDecision = CeqanetMaturityDecision.KEEP_PARTIAL
    reasons: list[str] = Field(min_length=1)
    blockers: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    next_gate: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("reasons", "blockers", "limitations")
    @classmethod
    def require_unique_nonblank_text(cls, values: list[str]) -> list[str]:
        """Reject blank or duplicate governance statements."""

        if any(not value.strip() for value in values):
            raise ValueError("maturity proposal text values must be nonblank")
        if len(values) != len(set(values)):
            raise ValueError("maturity proposal text values must be unique")
        return values

    @model_validator(mode="after")
    def require_conservative_decision(self) -> CeqanetSourceMaturityProposal:
        """Keep the proposal internally consistent with its non-authorizing scope."""

        if self.decision is not CeqanetMaturityDecision.KEEP_PARTIAL:
            raise ValueError("current maturity proposal must keep CEQAnet partial")
        if not self.blockers:
            raise ValueError("keep-partial proposals must preserve explicit blockers")
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return approval-significant content without timestamp or stored digest."""

        return self.model_dump(
            mode="json",
            exclude={"generated_at", "proposal_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical digest for proposal evidence and governance."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Raise when proposal content differs from its stored digest."""

        if self.proposal_digest != self.computed_digest():
            raise ValueError("CEQAnet source-maturity proposal digest mismatch")


class CeqanetSourceMaturityProposalVerification(BaseModel):
    """Independent verification of one source-maturity proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "ceqanet_source_maturity_proposal_verification.v1"
    ] = MATURITY_VERIFICATION_SCHEMA_VERSION
    passed: bool
    finding_count: int = Field(ge=0)
    findings: list[str]
    proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    live_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_result_consistency(
        self,
    ) -> CeqanetSourceMaturityProposalVerification:
        """Require pass state, finding count, and findings to agree."""

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal findings length")
        if self.passed != (self.finding_count == 0):
            raise ValueError("passed must agree with finding_count")
        return self
