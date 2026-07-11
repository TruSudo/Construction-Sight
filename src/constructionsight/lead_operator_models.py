"""Operator-facing models for persisted lead workflow records."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LeadOperatorRecordKind(StrEnum):
    """Persisted post-enrichment record families exposed to operators."""

    ENRICHMENT = "enrichment"
    REVIEW = "review"
    FINGERPRINT = "fingerprint"
    DUPLICATE = "duplicate"
    WORKFLOW = "workflow"
    EVENT = "event"
    LEDGER = "ledger"
    SHARE = "share"


class LeadOperatorRecord(BaseModel):
    """Normalized operator view over one persisted lead-related record."""

    record_kind: LeadOperatorRecordKind
    record_id: str = Field(min_length=1)
    status: str | None = None
    base_candidate_id: str | None = None
    workflow_id: str | None = None
    package_id: str | None = None
    lead_score: int | None = Field(default=None, ge=0, le=100)
    observed_created_at: str | None = None
    observed_updated_at: str | None = None
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-safe record payload."""

        return self.model_dump(mode="json")


class LeadWorkflowTransitionReport(BaseModel):
    """Audit-safe result of one persisted workflow transition."""

    workflow_id: str = Field(min_length=1)
    previous_status: str = Field(min_length=1)
    current_status: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    event_count: int = Field(ge=1)
    workflow_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-safe transition payload."""

        return self.model_dump(mode="json")
