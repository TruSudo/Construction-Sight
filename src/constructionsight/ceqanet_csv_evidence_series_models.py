"""Exact-schema models for governed CEQAnet CSV evidence series."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from constructionsight.ceqanet_csv_live_models import (
    CeqanetCsvLiveExecution,
    CeqanetCsvLiveVerification,
)
from constructionsight.ceqanet_csv_models import (
    CeqanetCsvExportKind,
    canonical_digest,
)

CSV_EVIDENCE_EXECUTION_SCHEMA_VERSION: Final = (
    "ceqanet_csv_evidence_execution.v1"
)
CSV_EVIDENCE_OBSERVATION_SCHEMA_VERSION: Final = (
    "ceqanet_csv_evidence_observation.v1"
)
CSV_EVIDENCE_SERIES_SCHEMA_VERSION: Final = "ceqanet_csv_evidence_series.v1"
CSV_EVIDENCE_SERIES_VERIFICATION_SCHEMA_VERSION: Final = (
    "ceqanet_csv_evidence_series_verification.v1"
)


class CeqanetCsvEvidenceSeriesStatus(StrEnum):
    """Conservative state for one official-CSV evidence series."""

    COLLECTING = "collecting"
    HALTED = "halted"
    READY_FOR_MATURITY_REVIEW = "ready_for_maturity_review"


class CeqanetCsvEvidenceExecution(BaseModel):
    """One policy-bound execution with its complete retained live envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_evidence_execution.v1"] = (
        CSV_EVIDENCE_EXECUTION_SCHEMA_VERSION
    )
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    explicit_execution_authorization_confirmed: Literal[True] = True
    authorization_granted_at: datetime
    authorized_utc_date: date
    request_count: Literal[1] = 1
    timeout_seconds: float = Field(gt=0, le=30.0)
    max_body_bytes: int = Field(ge=1, le=10_000_000)
    max_retained_rows: int = Field(ge=0, le=1_000)
    live_execution: CeqanetCsvLiveExecution
    live_verification: CeqanetCsvLiveVerification
    evidence_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("authorization_granted_at")
    @classmethod
    def normalize_authorization_time(cls, value: datetime) -> datetime:
        """Require an aware timestamp and normalize it to UTC."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("authorization_granted_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def require_execution_consistency(self) -> CeqanetCsvEvidenceExecution:
        """Keep authority, execution, and independent verification aligned."""

        executed_at = self.live_execution.executed_at
        if executed_at.tzinfo is None or executed_at.utcoffset() is None:
            raise ValueError("live execution timestamp must be timezone-aware")
        executed_at_utc = executed_at.astimezone(UTC)
        if executed_at_utc.date() != self.authorized_utc_date:
            raise ValueError(
                "authorized_utc_date must equal the live execution UTC date"
            )
        if self.authorization_granted_at > executed_at_utc:
            raise ValueError(
                "execution authorization cannot postdate the live request"
            )
        if self.authorization_granted_at.date() != self.authorized_utc_date:
            raise ValueError(
                "authorization_granted_at must fall on authorized_utc_date"
            )
        if (
            self.live_verification.execution_digest
            != self.live_execution.execution_digest
        ):
            raise ValueError(
                "live verification execution digest does not match live evidence"
            )
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return all policy and response evidence except the stored digest."""

        return self.model_dump(
            mode="json",
            exclude={"evidence_execution_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical complete evidence-execution digest."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Reject any policy or response evidence change."""

        if self.evidence_execution_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV evidence execution digest mismatch")


class CeqanetCsvEvidenceObservation(BaseModel):
    """Compact ledger entry bound to one complete evidence execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_evidence_observation.v1"] = (
        CSV_EVIDENCE_OBSERVATION_SCHEMA_VERSION
    )
    evidence_execution_artifact_ref: str = Field(min_length=1)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    live_execution_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    executed_at: datetime
    utc_date: date
    export_kind: CeqanetCsvExportKind
    sch_number: str = Field(pattern=r"^\d{10}$")
    document_id: int | None = Field(default=None, ge=1)
    request_url: str = Field(min_length=1)
    status_code: int | None = Field(default=None, ge=100, le=599)
    observed_body_byte_length: int = Field(ge=0)
    retained_body_complete: bool
    body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    inspection_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    verification_passed: bool
    verification_finding_count: int = Field(ge=0)
    verification_findings: list[str]
    successful: bool
    access_control_halt: bool
    observation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("evidence_execution_artifact_ref")
    @classmethod
    def require_repo_relative_artifact_ref(cls, value: str) -> str:
        """Reject ambiguous, absolute, or traversal-capable artifact references."""

        if value != value.strip() or "\\" in value:
            raise ValueError("evidence execution artifact ref must be normalized")
        path = PurePosixPath(value)
        if path.is_absolute() or not path.parts:
            raise ValueError("evidence execution artifact ref must be relative")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError(
                "evidence execution artifact ref cannot contain traversal segments"
            )
        if path.as_posix() != value:
            raise ValueError(
                "evidence execution artifact ref must use canonical POSIX form"
            )
        return value

    @field_validator("executed_at")
    @classmethod
    def normalize_execution_time(cls, value: datetime) -> datetime:
        """Require an aware timestamp and normalize it to UTC."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("executed_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("verification_findings")
    @classmethod
    def require_unique_nonblank_findings(cls, values: list[str]) -> list[str]:
        """Preserve exact independent findings without blanks or duplicates."""

        if any(not value.strip() for value in values):
            raise ValueError("verification findings must be nonblank")
        if len(values) != len(set(values)):
            raise ValueError("verification findings must be unique")
        return values

    @model_validator(mode="after")
    def require_observation_consistency(
        self,
    ) -> CeqanetCsvEvidenceObservation:
        """Keep compact observation facts internally exact."""

        if self.executed_at.date() != self.utc_date:
            raise ValueError("observation utc_date must equal executed_at UTC date")
        if self.export_kind is CeqanetCsvExportKind.PROJECT:
            if self.document_id is not None:
                raise ValueError("project observations cannot include document_id")
        elif self.document_id is None:
            raise ValueError("document observations require document_id")
        if self.verification_finding_count != len(self.verification_findings):
            raise ValueError(
                "verification_finding_count must equal verification findings length"
            )
        if self.verification_passed != (
            self.verification_finding_count == 0
        ):
            raise ValueError(
                "verification_passed must agree with verification findings"
            )
        if self.successful != self.verification_passed:
            raise ValueError(
                "successful must agree with independent live verification"
            )
        if self.successful:
            if self.status_code != 200:
                raise ValueError("successful observations require HTTP 200")
            if not self.retained_body_complete:
                raise ValueError(
                    "successful observations require a complete retained body"
                )
            if self.inspection_digest is None:
                raise ValueError(
                    "successful observations require an inspection digest"
                )
        if self.access_control_halt and self.successful:
            raise ValueError("access-control halt observations cannot be successful")
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return ledger-significant content without the stored digest."""

        return self.model_dump(mode="json", exclude={"observation_digest"})

    def computed_digest(self) -> str:
        """Return the canonical digest for this compact observation."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Reject any changed observation content."""

        if self.observation_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV evidence observation digest mismatch")


class CeqanetCsvEvidenceSeries(BaseModel):
    """Immutable snapshot of the governed official-CSV evidence ledger."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["ceqanet_csv_evidence_series.v1"] = (
        CSV_EVIDENCE_SERIES_SCHEMA_VERSION
    )
    source_name: str = Field(min_length=1)
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    policy_effective_date: date
    policy_expires_on: date
    observations: list[CeqanetCsvEvidenceObservation]
    series_sequence: int = Field(ge=0)
    predecessor_series_digest: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    observation_count: int = Field(ge=0)
    successful_observation_count: int = Field(ge=0)
    distinct_successful_utc_dates: list[date]
    observed_successful_export_kinds: list[CeqanetCsvExportKind]
    minimum_successful_observations: int = Field(ge=2)
    minimum_distinct_utc_dates: int = Field(ge=2)
    required_export_kinds: list[CeqanetCsvExportKind] = Field(min_length=1)
    status: CeqanetCsvEvidenceSeriesStatus
    halted_on: date | None = None
    halt_status_code: int | None = Field(default=None, ge=100, le=599)
    source_promotion_authorized: Literal[False] = False
    production_recurring_execution_authorized: Literal[False] = False
    next_gate: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    series_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("required_export_kinds", "observed_successful_export_kinds")
    @classmethod
    def require_unique_export_kinds(
        cls,
        values: list[CeqanetCsvExportKind],
    ) -> list[CeqanetCsvExportKind]:
        """Reject duplicate export scopes."""

        if len(values) != len(set(values)):
            raise ValueError("evidence series export kinds must be unique")
        return values

    @field_validator("distinct_successful_utc_dates")
    @classmethod
    def require_sorted_unique_dates(cls, values: list[date]) -> list[date]:
        """Require deterministic, unique successful UTC dates."""

        if values != sorted(set(values)):
            raise ValueError(
                "distinct successful UTC dates must be sorted and unique"
            )
        return values

    @model_validator(mode="after")
    def require_series_consistency(self) -> CeqanetCsvEvidenceSeries:
        """Enforce counts, daily bounds, halt finality, and readiness truth."""

        if self.policy_effective_date > self.policy_expires_on:
            raise ValueError("series policy dates are invalid")
        if self.observation_count != len(self.observations):
            raise ValueError("observation_count must equal observations length")
        if self.series_sequence != self.observation_count:
            raise ValueError(
                "series_sequence must equal the append-only observation count"
            )
        if self.series_sequence == 0:
            if self.predecessor_series_digest is not None:
                raise ValueError(
                    "empty evidence-series baseline cannot have a predecessor"
                )
        elif self.predecessor_series_digest is None:
            raise ValueError(
                "nonempty evidence series must bind its predecessor digest"
            )
        ordered = sorted(
            self.observations,
            key=lambda item: (
                item.executed_at,
                item.evidence_execution_digest,
            ),
        )
        if self.observations != ordered:
            raise ValueError("evidence observations must use deterministic order")
        refs = [
            item.evidence_execution_artifact_ref for item in self.observations
        ]
        execution_digests = [
            item.evidence_execution_digest for item in self.observations
        ]
        observation_digests = [
            item.observation_digest for item in self.observations
        ]
        if len(refs) != len(set(refs)):
            raise ValueError("evidence execution artifact refs must be unique")
        if len(execution_digests) != len(set(execution_digests)):
            raise ValueError("evidence execution digests must be unique")
        if len(observation_digests) != len(set(observation_digests)):
            raise ValueError("evidence observation digests must be unique")
        dates = [item.utc_date for item in self.observations]
        if len(dates) != len(set(dates)):
            raise ValueError("at most one evidence execution is allowed per UTC day")
        if any(item.policy_digest != self.policy_digest for item in self.observations):
            raise ValueError("every observation must bind the series policy digest")
        if any(
            item.utc_date < self.policy_effective_date
            or item.utc_date > self.policy_expires_on
            for item in self.observations
        ):
            raise ValueError("every observation must fall inside the policy window")
        successful = [item for item in self.observations if item.successful]
        if self.successful_observation_count != len(successful):
            raise ValueError(
                "successful_observation_count must equal successful observations"
            )
        successful_dates = sorted({item.utc_date for item in successful})
        if self.distinct_successful_utc_dates != successful_dates:
            raise ValueError(
                "distinct successful UTC dates do not match observations"
            )
        successful_kinds = sorted(
            {item.export_kind for item in successful},
            key=lambda item: item.value,
        )
        if self.observed_successful_export_kinds != successful_kinds:
            raise ValueError(
                "observed successful export kinds do not match observations"
            )

        halted = [
            item for item in self.observations if item.access_control_halt
        ]
        if halted:
            halt = halted[0]
            if len(halted) != 1 or self.observations[-1] != halt:
                raise ValueError(
                    "the first access-control halt must end the evidence series"
                )
            if self.status is not CeqanetCsvEvidenceSeriesStatus.HALTED:
                raise ValueError("a halt observation requires halted series status")
            if self.halted_on != halt.utc_date:
                raise ValueError("halted_on must match the halt observation")
            if self.halt_status_code != halt.status_code:
                raise ValueError(
                    "halt_status_code must match the halt observation"
                )
        else:
            if self.halted_on is not None or self.halt_status_code is not None:
                raise ValueError("non-halted series cannot include halt metadata")
            ready = (
                len(successful) >= self.minimum_successful_observations
                and len(successful_dates) >= self.minimum_distinct_utc_dates
                and set(successful_kinds) == set(self.required_export_kinds)
            )
            expected = (
                CeqanetCsvEvidenceSeriesStatus.READY_FOR_MATURITY_REVIEW
                if ready
                else CeqanetCsvEvidenceSeriesStatus.COLLECTING
            )
            if self.status is not expected:
                raise ValueError(
                    "series status does not match evidence completion criteria"
                )
        return self

    def evidence_payload(self) -> dict[str, Any]:
        """Return complete ledger content without timestamp or stored digest."""

        return self.model_dump(
            mode="json",
            exclude={"generated_at", "series_digest"},
        )

    def computed_digest(self) -> str:
        """Return the canonical digest for this immutable series snapshot."""

        return canonical_digest(self.evidence_payload())

    def assert_integrity(self) -> None:
        """Reject any changed series content."""

        if self.series_digest != self.computed_digest():
            raise ValueError("CEQAnet CSV evidence series digest mismatch")


class CeqanetCsvEvidenceSeriesVerification(BaseModel):
    """Independent verification of one evidence-series snapshot."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[
        "ceqanet_csv_evidence_series_verification.v1"
    ] = CSV_EVIDENCE_SERIES_VERIFICATION_SCHEMA_VERSION
    passed: bool
    finding_count: int = Field(ge=0)
    findings: list[str]
    policy_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    series_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    observation_count: int = Field(ge=0)
    successful_observation_count: int = Field(ge=0)
    ready_for_maturity_review: bool

    @model_validator(mode="after")
    def require_result_consistency(
        self,
    ) -> CeqanetCsvEvidenceSeriesVerification:
        """Require pass state, finding count, and findings to agree."""

        if self.finding_count != len(self.findings):
            raise ValueError("finding_count must equal findings length")
        if self.passed != (self.finding_count == 0):
            raise ValueError("passed must agree with finding_count")
        if self.ready_for_maturity_review and not self.passed:
            raise ValueError(
                "failed series verification cannot claim maturity readiness"
            )
        return self
