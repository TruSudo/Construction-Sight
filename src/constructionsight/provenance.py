"""Evidence and provenance models for ConstructionSight."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, computed_field, model_validator

from constructionsight.domain_types import ConfidenceBand, confidence_band


class ProvenanceConfidenceBasis(StrEnum):
    """Deterministic confidence derivation available to generic provenance."""

    UNASSESSED = "unassessed"
    DIRECT_OBSERVATION = "direct_observation"
    DETERMINISTIC_NORMALIZATION = "deterministic_normalization"


_DERIVED_CONFIDENCE = {
    ProvenanceConfidenceBasis.UNASSESSED: 0,
    ProvenanceConfidenceBasis.DIRECT_OBSERVATION: 60,
    ProvenanceConfidenceBasis.DETERMINISTIC_NORMALIZATION: 75,
}


class Provenance(BaseModel):
    """Evidence attached to a normalized public-record assertion.

    Generic provenance is intentionally non-authoritative. It records retained
    evidence and deterministic derivation context, but cannot self-assert a
    verified state. Stronger verification belongs to reviewed assurance
    services that validate independent evidence and reviewer authority.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    captured_at: datetime | None = None
    adapter_family: str | None = None
    raw_reference: str | None = None
    evidence_text: str | None = None
    confidence_basis: ProvenanceConfidenceBasis = ProvenanceConfidenceBasis.UNASSESSED
    notes: str | None = None

    @model_validator(mode="after")
    def require_evidence_for_assessed_confidence(self) -> Provenance:
        """Require retained evidence and derivation context for nonzero confidence."""

        if self.confidence_basis is ProvenanceConfidenceBasis.UNASSESSED:
            return self
        if self.evidence_text is None or not self.evidence_text.strip():
            raise ValueError("assessed provenance requires retained evidence_text")
        if self.confidence_basis is ProvenanceConfidenceBasis.DIRECT_OBSERVATION:
            if self.source_url is None and not self.raw_reference:
                raise ValueError(
                    "direct observation requires a source URL or raw reference"
                )
            return self
        if not self.adapter_family:
            raise ValueError(
                "deterministic normalization requires adapter_family derivation provenance"
            )
        return self

    @computed_field
    def evidence_sha256(self) -> str | None:
        """Return the digest of retained evidence bytes represented by evidence_text."""

        if self.evidence_text is None:
            return None
        return hashlib.sha256(self.evidence_text.encode("utf-8")).hexdigest()

    @computed_field
    def lineage_id(self) -> str:
        """Return a deterministic source-lineage identity, not a caller assertion."""

        source_url = str(self.source_url) if self.source_url is not None else ""
        payload = "|".join(
            [self.source_name.strip(), source_url, self.adapter_family or ""]
        )
        return f"provenance-lineage:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"

    @computed_field
    def confidence_score(self) -> int:
        """Return confidence derived only from the declared supported basis."""

        return _DERIVED_CONFIDENCE[self.confidence_basis]

    @computed_field
    def verified(self) -> bool:
        """Generic provenance cannot self-certify an authoritative verification."""

        return False

    @property
    def band(self) -> ConfidenceBand:
        """Return the confidence band without promoting score to verification."""

        return confidence_band(self.confidence_score)
