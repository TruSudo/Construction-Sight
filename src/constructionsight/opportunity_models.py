"""Opportunity and lead-candidate models for ConstructionSight."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.domain_types import ConfidenceBand
from constructionsight.intake_models import FactConfidence


class OpportunityTransitionKind(StrEnum):
    """Lead-producing transition signals discovered from lawful intake evidence."""

    SOURCE_OBSERVED = "source_observed"
    CEQA_SIGNAL = "ceqa_signal"
    PERMIT_APPLICATION = "permit_application"
    PERMIT_ISSUED = "permit_issued"
    CONTRACTOR_IDENTIFIED = "contractor_identified"
    VALUATION_CHANGED = "valuation_changed"
    INSPECTION_MOVEMENT = "inspection_movement"
    EXPIRATION_OR_FINALIZATION = "expiration_or_finalization"
    SITE_ANCHOR = "site_anchor"
    CONTACT_CHANNEL = "contact_channel"
    AGENCY_ANCHOR = "agency_anchor"
    CONSTRUCTION_SCOPE = "construction_scope"


class OpportunityReadiness(StrEnum):
    """How ready an opportunity candidate is for sales action."""

    NOT_QUALIFIED = "not_qualified"
    MONITOR = "monitor"
    RESEARCH_READY = "research_ready"
    OUTREACH_READY = "outreach_ready"


class OpportunityPriority(StrEnum):
    """Operational priority for lead generation."""

    HOLD = "hold"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OpportunityTransitionEvent(BaseModel):
    """One transition signal that may make a construction record actionable."""

    event_id: str = Field(min_length=1)
    event_kind: OpportunityTransitionKind
    label: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    confidence: FactConfidence = FactConfidence.SOURCE_CLAIMED
    score_delta: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1)

    @field_validator("fact_ids")
    @classmethod
    def require_unique_fact_ids(cls, values: list[str]) -> list[str]:
        """Keep transition evidence deterministic and non-duplicative."""

        if len(values) != len(set(values)):
            raise ValueError("fact_ids must contain unique values")
        return values


class OpportunityCandidate(BaseModel):
    """Source-neutral opportunity candidate derived from a universal intake record."""

    candidate_id: str = Field(min_length=1)
    intake_id: str = Field(min_length=1)
    evidence_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    source_url: str | None = None
    title_hint: str | None = None
    jurisdiction_hint: str | None = None
    site_hints: dict[str, str] = Field(default_factory=dict)
    contact_hints: dict[str, str] = Field(default_factory=dict)
    source_hints: dict[str, str] = Field(default_factory=dict)
    transition_events: list[OpportunityTransitionEvent] = Field(default_factory=list)
    lead_score: int = Field(ge=0, le=100)
    readiness: OpportunityReadiness
    priority: OpportunityPriority
    confidence_band: ConfidenceBand
    recommended_action: str = Field(min_length=1)
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("site_hints", "contact_hints", "source_hints")
    @classmethod
    def require_non_blank_hint_values(cls, values: dict[str, str]) -> dict[str, str]:
        """Reject blank hint keys or values."""

        for key, value in values.items():
            if not key.strip() or not value.strip():
                raise ValueError("hint dictionaries cannot contain blank keys or values")
        return values

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Keep candidate narrative fields deterministic."""

        if len(values) != len(set(values)):
            raise ValueError("candidate text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_score_to_match_priority(self) -> OpportunityCandidate:
        """Prevent high-priority candidates from carrying no transition evidence."""

        if self.priority != OpportunityPriority.HOLD and not self.transition_events:
            raise ValueError("non-hold opportunity candidates require transition events")
        if self.lead_score == 0 and self.readiness != OpportunityReadiness.NOT_QUALIFIED:
            raise ValueError("zero-score candidates must be not qualified")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe candidate payload."""

        return self.model_dump(mode="json")
