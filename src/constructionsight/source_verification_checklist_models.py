"""Source verification checklist models."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChecklistItemStatus(StrEnum):
    """Status for one manual source-verification checklist item."""

    NOT_CHECKED = "not_checked"
    OBSERVED = "observed"
    NOT_OBSERVED = "not_observed"
    BLOCKED = "blocked"
    FAILED = "failed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"


class SourceVerificationChecklistStatus(StrEnum):
    """Conservative source-verification checklist outcome."""

    NOT_CHECKED = "not_checked"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    PUBLIC_ENTRY_REACHABLE = "public_entry_reachable"
    QUERY_BEHAVIOR_OBSERVED = "query_behavior_observed"
    DETAIL_BEHAVIOR_OBSERVED = "detail_behavior_observed"
    BLOCKED = "blocked"
    FAILED = "failed"
    PARTIAL_CANDIDATE = "partial_candidate"
    VERIFIED_CANDIDATE_REVIEW = "verified_candidate_review"


class SourceVerificationObservation(BaseModel):
    """Optional operator observation for a source checklist row."""

    source_key: str | None = None
    source_name: str | None = None
    public_entry_observed: bool | None = None
    query_behavior_observed: bool | None = None
    result_list_observed: bool | None = None
    detail_page_observed: bool | None = None
    access_barrier_observed: bool | None = None
    terms_review_observed: bool | None = None
    notes: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("evidence_refs")
    @classmethod
    def require_unique_evidence_refs(cls, values: list[str]) -> list[str]:
        """Reject duplicate evidence references."""

        if len(values) != len(set(values)):
            raise ValueError("evidence_refs must contain unique values")
        return values


class SourceVerificationChecklistRow(BaseModel):
    """Manual verification checklist row for one source."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    platform_family: str = Field(min_length=1)
    original_url: str = Field(min_length=1)
    final_url: str | None = None
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    redirect_classification: str = Field(min_length=1)
    registry_status: str = Field(min_length=1)
    adapter_status: str = Field(min_length=1)
    readiness_status: str = Field(min_length=1)
    checklist_status: SourceVerificationChecklistStatus
    public_entry_page: ChecklistItemStatus
    query_behavior: ChecklistItemStatus
    result_list: ChecklistItemStatus
    detail_page: ChecklistItemStatus
    access_barrier: ChecklistItemStatus
    terms_review: ChecklistItemStatus
    recommendation: str = Field(min_length=1)
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    observation_notes: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations", "evidence_refs")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate text values."""

        if len(values) != len(set(values)):
            raise ValueError("checklist text lists must contain unique values")
        return values


class SourceVerificationChecklistReport(BaseModel):
    """Aggregated manual source-verification checklist report."""

    source_count: int = Field(ge=0)
    status_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[SourceVerificationChecklistRow] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_rows(
        cls,
        rows: list[SourceVerificationChecklistRow],
    ) -> SourceVerificationChecklistReport:
        """Build checklist report summary counts from rows."""

        return cls(
            source_count=len(rows),
            status_counts=dict(Counter(row.checklist_status.value for row in rows)),
            rows=rows,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report payload."""

        return self.model_dump(mode="json")
