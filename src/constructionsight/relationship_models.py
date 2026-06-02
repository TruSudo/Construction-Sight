"""Relationship graph domain models for ConstructionSight."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from constructionsight.domain_types import RelationshipType
from constructionsight.provenance import Provenance


class RelationshipRecord(BaseModel):
    """Evidence-bound directed relationship between two normalized records."""

    relationship_key: str = Field(min_length=1)
    subject_key: str = Field(min_length=1)
    relationship_type: RelationshipType
    object_key: str = Field(min_length=1)
    confidence_score: int = Field(default=0, ge=0, le=100)
    provenance: list[Provenance] = Field(default_factory=list)
    notes: str | None = None

    @property
    def is_high_confidence(self) -> bool:
        """Return true when relationship confidence is high enough for graph emphasis."""

        return self.confidence_score >= 75

    @model_validator(mode="after")
    def require_evidence_for_high_confidence(self) -> "RelationshipRecord":
        """Require provenance before a high-confidence relationship can be asserted."""

        if self.confidence_score >= 75 and not self.provenance:
            raise ValueError("high-confidence relationships require provenance")
        return self
