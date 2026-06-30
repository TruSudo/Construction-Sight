"""Opportunity enrichment models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.domain_types import ConfidenceBand, confidence_band


class EnrichmentSignalKind(StrEnum):
    """Cross-layer signal kinds that affect opportunity scoring."""

    PARCEL_SITE = "parcel_site"
    PERMIT_TRANSITION = "permit_transition"
    CONTRACTOR_IDENTITY = "contractor_identity"
    DECISION_SIGNAL = "decision_signal"


class OpportunityEnrichmentSignal(BaseModel):
    """One score-bearing enrichment signal."""

    signal_key: str = Field(min_length=1)
    signal_kind: EnrichmentSignalKind
    label: str = Field(min_length=1)
    score_delta: int = Field(ge=0, le=100)
    confidence_score: int = Field(default=0, ge=0, le=100)
    reason: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("limitations")
    @classmethod
    def require_unique_limitations(cls, values: list[str]) -> list[str]:
        """Reject duplicate limitations."""

        if len(values) != len(set(values)):
            raise ValueError("enrichment signal limitations must contain unique values")
        return values


class OpportunityEnrichmentReport(BaseModel):
    """Aggregated opportunity enrichment result."""

    report_id: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    lead_score: int = Field(ge=0, le=100)
    confidence_score: int = Field(default=0, ge=0, le=100)
    confidence_band: ConfidenceBand = ConfidenceBand.UNKNOWN
    signals: list[OpportunityEnrichmentSignal] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate reasons or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("opportunity enrichment text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_confidence_consistency(self) -> OpportunityEnrichmentReport:
        """Require confidence band to match score."""

        expected = confidence_band(self.confidence_score)
        if self.confidence_band != expected:
            raise ValueError("confidence_band must match confidence_score")
        if self.lead_score > 0 and not self.signals:
            raise ValueError("positive enrichment score requires signals")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe enrichment payload."""

        return self.model_dump(mode="json")
