"""Operator-facing models for persisted upstream intelligence records."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class UpstreamOperatorRecordKind(StrEnum):
    """Persisted upstream record families exposed to operators."""

    PERMIT_SNAPSHOT = "permit_snapshot"
    PERMIT_TRANSITION = "permit_transition"
    CONTRACTOR = "contractor"
    DECISION = "decision"
    PARCEL = "parcel"
    PARCEL_SOURCE_EVIDENCE = "parcel_source_evidence"
    PARCEL_SOURCE_VERIFICATION = "parcel_source_verification"
    PARCEL_COUNTY_COVERAGE = "parcel_county_coverage"
    PARCEL_OBSERVATION = "parcel_observation"
    PARCEL_CURRENT_SELECTION = "parcel_current_selection"
    PARCEL_ASSURANCE = "parcel_assurance"
    SITE_RESOLUTION = "site_resolution"


class UpstreamOperatorRecord(BaseModel):
    """Normalized operator envelope over one persisted upstream record."""

    record_kind: UpstreamOperatorRecordKind
    record_id: str = Field(min_length=1)
    status: str | None = None
    source_key: str | None = None
    source_record_id: str | None = None
    site_key: str | None = None
    apn: str | None = None
    county: str | None = None
    confidence_score: int | None = Field(default=None, ge=0, le=100)
    observed_at: str | None = None
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe normalized record envelope."""

        return self.model_dump(mode="json")
