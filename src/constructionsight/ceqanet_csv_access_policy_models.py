"""Exact-schema governance models for bounded CEQAnet CSV evidence access."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.ceqanet_csv_models import CeqanetCsvExportKind, canonical_digest

CSV_ACCESS_POLICY_SCHEMA_VERSION: Final = "ceqanet_csv_access_policy.v1"
CSV_ACCESS_POLICY_VERIFICATION_SCHEMA_VERSION: Final = (
    "ceqanet_csv_access_policy_verification.v1"
)


class CeqanetCsvAccessPolicyStatus(StrEnum):
    """Authority state for one bounded official-CSV evidence policy."""

    READY_FOR_EXPLICIT_EVIDENCE_COLLECTION = (
        "ready_for_explicit_evidence_collection"
    )


class CeqanetCsvAccessPolicy(BaseModel):
    """Digest-bound policy that authorizes evidence collection, not production."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_access_policy.v1"] = (
        CSV_ACCESS_POLICY_SCHEMA_VERSION
    )
    source_name: str = Field(min_length=1)
    registry_status: Literal["partial"] = "partial"
    source_registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    maturity_proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    live_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    official_host: Literal["ceqanet.lci.ca.gov"] = "ceqanet.lci.ca.gov"
    official_path: Literal["/Search"] = "/Search"
    allowed_export_kinds: list[CeqanetCsvExportKind] = Field(min_length=1)
    method: Literal["GET"] = "GET"
    max_requests_per_execution: Literal[1] = 1
    max_executions_per_utc_day: Literal[1] = 1
    retry_count: Literal[0] = 0
    timeout_seconds: float = Field(default=20.0, gt=0, le=30.0)
    max_body_bytes: int = Field(default=10_000_000, ge=1, le=10_000_000)
    retain_complete_body: Literal[True] = True
    require_independent_verification: Literal[True] = True
    explicit_execution_authorization_required: Literal[True] = True
    attachment_download_authorized: Literal[False] = False
    html_automation_authorized: Literal[False] = False
    credential_use_authorized: Literal[False] = False
    captcha_handling_authorized: Literal[False] = False
    access_control_bypass_authorized: Literal[False] = False
    persistence_mutation_authorized: Literal[False] = False
    registry_mutation_authorized: Literal[False] = False
    source_promotion_authorized: Literal[False] = False
    production_recurring_execution_authorized: Literal[False] = False
    halt_status_codes: list[int] = Field(min_length=1)
    effective_date: date
    expires_on: date
    minimum_successful_observations: int = Field(ge=2)
    minimum_distinct_utc_dates: int = Field(ge=2)
    required_evidence_export_kinds: list[CeqanetCsvExportKind] = Field(
        min_length=1
    )
    policy_status: CeqanetCsvAccessPolicyStatus = (
        CeqanetCsvAccessPolicyStatus.READY_FOR_EXPLICIT_EVIDENCE_COLLECTION
    )
    production_blockers: list[str] = Field(min_length=1)
    limitations: list[str] = Field(min_length=1)
    next_gate: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("allowed_export_kinds", "required_evidence_export_kinds")
    @classmethod
    def require_unique_export_kinds(
        cls,
        values: list[CeqanetCsvExportKind],
    ) -> list[CeqanetCsvExportKind]:
        """Reject duplicate export scopes."""

        if len(values) != len(set(values)):
            raise ValueError("CSV access policy export kinds must be unique")
        return values

    @field_validator("halt_status_codes")
    @classmethod
    def require_unique_halt_codes(cls, values: list[int]) -> list[int]:
        """Require unique access-control response codes."""

        if len(values) != len(set(values)):
            raise ValueError("CSV access policy halt status codes must be unique")
        if any(value < 100 or value > 599 for value in values):
            raise ValueError("CSV access policy halt status codes must be HTTP statuses")
        return values

    @field_validator("production_blockers", "limitations")
    @classmethod
    def require_unique_nonblank_text(cls, values: list[str]) -> list[str]:
        """Reject blank or duplicate policy statements."""

        if any(not value.strip() for value in values):
            raise ValueError("CSV access policy text values must be nonblank")
        if len(values) != len(set(values)):
            raise ValueError("CSV access policy text values must be unique")
        return values

    @model_validator(mode="after")
    def require_bounded_policy_consistency(self) -> CeqanetCsvAccessPolicy:
        """Keep evidence authority time-bounded and internally consistent."""

        if self.effective_date > self.expires_on:
            raise ValueError("policy effective_date must be on or before expires_on")
        if (self.expires_on - self.effective_date).days > 31:
            raise ValueError("CSV access policy authority cannot exceed 31 days")
        if set(self.required_evidence_export_kinds) != set(
            self.allowed_export_kinds
        ):
            raise ValueError(
                "required evidence export kinds must equal allowed export kinds"
            )
        if self.minimum_distinct_utc_dates > self.minimum_successful_observations:
            raise ValueError(
                "distinct evidence dates cannot exceed successful observations"
            )
        if not self.production_blockers:
            raise ValueError("evidence policies must preserve production blockers")
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return authority-significant content without timestamp or digest."""

        return self.model_dump(
            mode="json",
            exclude={"generated_at", "policy_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical digest for policy evidence and authority."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Raise when policy content differs from its stored digest."""

        if self.policy_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV access policy digest mismatch")


class CeqanetCsvAccessPolicyVerification(BaseModel):
    """Independent verification of one bounded CSV access policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "ceqanet_csv_access_policy_verification.v1"
    ] = CSV_ACCESS_POLICY_VERIFICATION_SCHEMA_VERSION
    passed: bool
    finding_count: int = Field(ge=0)
    findings: list[str]
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_registry_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    maturity_proposal_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    live_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    replay_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def require_result_consistency(
        self,
    ) -> CeqanetCsvAccessPolicyVerification:
        """Require pass state, finding count, and findings to agree."""

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal findings length")
        if self.passed != (self.finding_count == 0):
            raise ValueError("passed must agree with finding_count")
        return self
