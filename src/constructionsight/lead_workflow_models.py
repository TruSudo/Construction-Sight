"""Lead workflow status models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class LeadWorkflowStatus(StrEnum):
    """Operational status for a lead after review and dedupe."""

    HOLD = "hold"
    MONITOR = "monitor"
    REVIEW = "review"
    READY = "ready"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED_SUCCESS = "closed_success"
    CLOSED_NO_FIT = "closed_no_fit"


class LeadWorkflowEvent(BaseModel):
    """One lead workflow status event."""

    event_id: str = Field(min_length=1)
    previous_status: LeadWorkflowStatus | None = None
    current_status: LeadWorkflowStatus
    reason: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LeadWorkflowRecord(BaseModel):
    """Lead workflow record after review and dedupe."""

    workflow_id: str = Field(min_length=1)
    package_id: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    fingerprint_key: str | None = None
    status: LeadWorkflowStatus
    lead_score: int = Field(ge=0, le=100)
    events: list[LeadWorkflowEvent] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("notes", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate notes or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("lead workflow text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_status_event_consistency(self) -> LeadWorkflowRecord:
        """Require the latest event to match current status when events exist."""

        if self.events and self.events[-1].current_status != self.status:
            raise ValueError("latest workflow event must match record status")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe workflow payload."""

        return self.model_dump(mode="json")
