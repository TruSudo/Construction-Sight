"""Lead review package models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class LeadReviewStatus(StrEnum):
    """Review status for a lead package."""

    HOLD = "hold"
    MONITOR = "monitor"
    REVIEW_REQUIRED = "review_required"
    READY = "ready"


class LeadReviewItem(BaseModel):
    """One recommended next step for a lead package."""

    item_key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    blocked_by_limitations: bool = False


class LeadReviewPackage(BaseModel):
    """Reviewable package before any external action."""

    package_id: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    lead_score: int = Field(ge=0, le=100)
    status: LeadReviewStatus
    summary: str = Field(min_length=1)
    items: list[LeadReviewItem] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    review_note: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("evidence_notes", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate evidence notes or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("lead review text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_status_consistency(self) -> LeadReviewPackage:
        """Keep status honest relative to next steps and limitations."""

        if self.status == LeadReviewStatus.READY and not self.items:
            raise ValueError("ready lead packages require review items")
        if self.status == LeadReviewStatus.READY and self.limitations:
            raise ValueError("ready lead packages cannot carry unresolved limitations")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe lead-review payload."""

        return self.model_dump(mode="json")
