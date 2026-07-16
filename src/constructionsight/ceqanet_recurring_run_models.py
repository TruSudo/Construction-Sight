"""Governed CEQAnet recurring-run definition and execution models."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

DEFINITION_SCHEMA_VERSION: Final = "ceqanet_recurring_run_definition.v1"
MANIFEST_SCHEMA_VERSION: Final = "ceqanet_recurring_run_manifest.v1"
EXECUTION_SCHEMA_VERSION: Final = "ceqanet_recurring_run_execution.v1"
VERIFICATION_SCHEMA_VERSION: Final = "ceqanet_recurring_run_verification.v1"


class CeqanetRunReadiness(StrEnum):
    """Readiness state for one governed recurring-run definition."""

    BLOCKED = "blocked"
    READY_FOR_MANUAL_EXECUTION = "ready_for_manual_execution"


class CeqanetWindowField(StrEnum):
    """Date field bounded by one recurring-run window."""

    RECEIVED = "received"
    POSTED = "posted"


class CeqanetAccessAssumptions(BaseModel):
    """Operator-reviewed lawful-access assumptions bound to a run definition."""

    requires_login: bool = False
    has_captcha: bool = False
    robots_disallows_collection: bool = False
    terms_disallow_collection: bool = False
    paywalled: bool = False

    @property
    def has_blocker(self) -> bool:
        """Return true when any access assumption blocks collection."""

        return any(
            (
                self.requires_login,
                self.has_captcha,
                self.robots_disallows_collection,
                self.terms_disallow_collection,
                self.paywalled,
            )
        )


class CeqanetRecurringQueryTemplate(BaseModel):
    """Stable CEQAnet filters combined with an explicit run window."""

    counties: list[str] = Field(default_factory=list)
    document_types: list[str] = Field(default_factory=list)
    lead_agencies: list[str] = Field(default_factory=list)
    text_terms: list[str] = Field(default_factory=list)
    high_signal_only: bool = False
    window_field: CeqanetWindowField = CeqanetWindowField.RECEIVED
    page_size: int = Field(default=25, ge=1, le=100)
    max_pages: int = Field(default=1, ge=1, le=10)

    @field_validator("counties", "document_types", "lead_agencies", "text_terms")
    @classmethod
    def require_unique_nonblank_values(cls, values: list[str]) -> list[str]:
        """Reject blank or duplicate query values."""

        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("query template values must be nonblank")
        if len(normalized) != len(set(normalized)):
            raise ValueError("query template values must be unique")
        return normalized

    @model_validator(mode="after")
    def reject_unsupported_text_terms(self) -> CeqanetRecurringQueryTemplate:
        """Reject filters not represented by the verified CEQAnet search contract."""

        if self.text_terms:
            raise ValueError(
                "CEQAnet recurring-run text_terms are unsupported by the verified search contract"
            )
        return self


class CeqanetRecurringRunDefinition(BaseModel):
    """Immutable reviewed definition for a recurring CEQAnet run family."""

    schema_version: Literal["ceqanet_recurring_run_definition.v1"] = DEFINITION_SCHEMA_VERSION
    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    registry_public_url: str = Field(min_length=1)
    execution_base_url: str = Field(min_length=1)
    source_registry_digest: str = Field(min_length=64, max_length=64)
    checklist_evidence_digest: str = Field(min_length=64, max_length=64)
    registry_verification_status: str = Field(min_length=1)
    checklist_status: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    access_assumptions: CeqanetAccessAssumptions
    query_template: CeqanetRecurringQueryTemplate
    timeout_seconds: float = Field(default=20.0, gt=0)
    max_body_chars: int = Field(default=50_000, ge=1)
    readiness: CeqanetRunReadiness
    blockers: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    definition_digest: str = Field(min_length=64, max_length=64)

    @field_validator("evidence_refs", "blockers", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate evidentiary or governance text."""

        if len(values) != len(set(values)):
            raise ValueError("definition text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_readiness_consistency(self) -> CeqanetRecurringRunDefinition:
        """Keep readiness and blocker state internally consistent."""

        if self.readiness is CeqanetRunReadiness.BLOCKED and not self.blockers:
            raise ValueError("blocked run definitions must contain blockers")
        if (
            self.readiness is CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION
            and self.blockers
        ):
            raise ValueError("ready run definitions cannot contain blockers")
        return self

    def approval_payload(self) -> dict[str, Any]:
        """Return approval-significant content without timestamps or digest."""

        return self.model_dump(
            mode="json",
            exclude={"generated_at", "definition_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical digest for approval-significant content."""

        return canonical_digest(self.approval_payload())

    def assert_integrity(self) -> None:
        """Raise when the stored digest does not match definition content."""

        if self.definition_digest != self.computed_digest():
            raise ValueError("CEQAnet recurring-run definition digest mismatch")


class CeqanetRecurringRunManifest(BaseModel):
    """Immutable exact-window manifest derived from one reviewed definition."""

    schema_version: Literal["ceqanet_recurring_run_manifest.v1"] = MANIFEST_SCHEMA_VERSION
    run_id: str = Field(min_length=64, max_length=64)
    definition_digest: str = Field(min_length=64, max_length=64)
    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    execution_base_url: str = Field(min_length=1)
    window_field: CeqanetWindowField
    window_start: date
    window_end: date
    query: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = Field(gt=0)
    max_body_chars: int = Field(ge=1)
    access_assumptions: CeqanetAccessAssumptions
    readiness: CeqanetRunReadiness
    blockers: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    operator_live_authorization_required: bool = True
    persistence_authorized: bool = False
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    manifest_digest: str = Field(min_length=64, max_length=64)

    @field_validator("blockers", "limitations")
    @classmethod
    def require_unique_manifest_text(cls, values: list[str]) -> list[str]:
        """Reject duplicate manifest governance text."""

        if len(values) != len(set(values)):
            raise ValueError("manifest text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def validate_manifest_state(self) -> CeqanetRecurringRunManifest:
        """Validate exact-window and authorization invariants."""

        if self.window_start > self.window_end:
            raise ValueError("window_start must be on or before window_end")
        if not self.operator_live_authorization_required:
            raise ValueError("recurring-run manifests must require explicit live authorization")
        if self.persistence_authorized:
            raise ValueError("recurring-run manifests cannot authorize persistence")
        if self.readiness is CeqanetRunReadiness.BLOCKED and not self.blockers:
            raise ValueError("blocked manifests must contain blockers")
        if (
            self.readiness is CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION
            and self.blockers
        ):
            raise ValueError("ready manifests cannot contain blockers")
        return self

    def approval_payload(self) -> dict[str, Any]:
        """Return manifest content excluding timestamp and stored digest."""

        return self.model_dump(
            mode="json",
            exclude={"generated_at", "manifest_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical manifest digest."""

        return canonical_digest(self.approval_payload())

    def assert_integrity(self) -> None:
        """Raise when the manifest content has changed."""

        if self.manifest_digest != self.computed_digest():
            raise ValueError("CEQAnet recurring-run manifest digest mismatch")


class CeqanetRecurringRunExecution(BaseModel):
    """One bounded live attempt tied to an immutable run manifest."""

    schema_version: Literal["ceqanet_recurring_run_execution.v1"] = EXECUTION_SCHEMA_VERSION
    run_id: str = Field(min_length=64, max_length=64)
    attempt_sequence: int = Field(ge=1)
    attempt_id: str = Field(min_length=64, max_length=64)
    definition_digest: str = Field(min_length=64, max_length=64)
    manifest_digest: str = Field(min_length=64, max_length=64)
    source_key: str = Field(min_length=1)
    execution_report: dict[str, Any] = Field(default_factory=dict)
    network_executed: bool
    persistence_mutated: bool = False
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    execution_digest: str = ""

    @model_validator(mode="after")
    def validate_execution_state(self) -> CeqanetRecurringRunExecution:
        """Reject persistence mutation and initialize new execution evidence digest."""

        if self.persistence_mutated:
            raise ValueError("recurring-run execution cannot mutate persistence")
        if not self.execution_digest:
            object.__setattr__(self, "execution_digest", self.computed_digest())
        elif len(self.execution_digest) != 64:
            raise ValueError("execution_digest must contain 64 characters")
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return the complete execution evidence excluding timestamp and digest."""

        return self.model_dump(
            mode="json",
            exclude={"executed_at", "execution_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical digest of the complete retained execution evidence."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Raise when any retained execution evidence has changed."""

        if self.execution_digest != self.computed_digest():
            raise ValueError("CEQAnet recurring-run execution digest mismatch")


class CeqanetRecurringRunVerification(BaseModel):
    """Verification result for definition, manifest, and execution agreement."""

    schema_version: Literal["ceqanet_recurring_run_verification.v1"] = (
        VERIFICATION_SCHEMA_VERSION
    )
    passed: bool
    finding_count: int = Field(ge=0)
    findings: list[str] = Field(default_factory=list)
    run_id: str = Field(min_length=64, max_length=64)
    definition_digest: str = Field(min_length=64, max_length=64)
    manifest_digest: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def require_count_consistency(self) -> CeqanetRecurringRunVerification:
        """Require finding count and pass state to agree with findings."""

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal the number of findings")
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
