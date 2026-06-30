"""Source promotion plan models."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SourcePromotionPlanAction(StrEnum):
    """Dry-run source promotion plan action."""

    KEEP_UNVERIFIED = "keep_unverified"
    MARK_BLOCKED_CANDIDATE = "mark_blocked_candidate"
    MARK_FAILED_CANDIDATE = "mark_failed_candidate"
    MARK_PARTIAL_CANDIDATE = "mark_partial_candidate"
    VERIFIED_CANDIDATE_REVIEW = "verified_candidate_review"


class SourcePromotionPlanRow(BaseModel):
    """Dry-run source promotion plan row."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    platform_family: str = Field(min_length=1)
    original_url: str = Field(min_length=1)
    final_url: str | None = None
    registry_status: str = Field(min_length=1)
    adapter_status: str = Field(min_length=1)
    readiness_status: str = Field(min_length=1)
    checklist_status: str = Field(min_length=1)
    planned_action: SourcePromotionPlanAction
    proposed_registry_status: str | None = None
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations", "evidence_refs")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate text values."""

        if len(values) != len(set(values)):
            raise ValueError("promotion plan text lists must contain unique values")
        return values


class SourcePromotionPlanReport(BaseModel):
    """Aggregated dry-run source promotion plan."""

    source_count: int = Field(ge=0)
    action_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[SourcePromotionPlanRow] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_rows(cls, rows: list[SourcePromotionPlanRow]) -> SourcePromotionPlanReport:
        """Build plan summary counts from rows."""

        return cls(
            source_count=len(rows),
            action_counts=dict(Counter(row.planned_action.value for row in rows)),
            rows=rows,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe report payload."""

        return self.model_dump(mode="json")
