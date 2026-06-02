"""Evidence and provenance models for ConstructionSight."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from constructionsight.domain_types import ConfidenceBand, confidence_band


class Provenance(BaseModel):
    """Evidence attached to a normalized public-record assertion."""

    source_name: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    captured_at: datetime | None = None
    adapter_family: str | None = None
    raw_reference: str | None = None
    evidence_text: str | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    verified: bool = False
    notes: str | None = None

    @property
    def band(self) -> ConfidenceBand:
        """Return the confidence band for this evidence record."""

        return confidence_band(self.confidence_score)
