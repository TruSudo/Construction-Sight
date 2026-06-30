"""Lead duplicate suppression models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class LeadDuplicateStatus(StrEnum):
    """Duplicate suppression result status."""

    UNIQUE = "unique"
    DUPLICATE = "duplicate"
    REVIEW_NEEDED = "review_needed"


class LeadFingerprint(BaseModel):
    """Stable fingerprint for duplicate lead detection."""

    fingerprint_key: str = Field(min_length=1)
    base_candidate_id: str = Field(min_length=1)
    site_key: str | None = None
    source_key: str | None = None
    source_record_id: str | None = None
    normalized_title: str | None = None
    lead_score: int = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_some_match_basis(self) -> LeadFingerprint:
        """Require at least one dedupe basis beyond candidate id."""

        if not any(
            [
                self.site_key,
                self.source_key and self.source_record_id,
                self.normalized_title,
            ]
        ):
            raise ValueError("lead fingerprint requires site, source record, or title basis")
        return self


class LeadDuplicateResult(BaseModel):
    """Result of comparing one lead fingerprint with existing fingerprints."""

    result_id: str = Field(min_length=1)
    status: LeadDuplicateStatus
    candidate: LeadFingerprint
    matched_fingerprint_keys: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("matched_fingerprint_keys", "reasons", "limitations")
    @classmethod
    def require_unique_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate values."""

        if len(values) != len(set(values)):
            raise ValueError("duplicate result lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_duplicate_match_consistency(self) -> LeadDuplicateResult:
        """Keep duplicate status consistent with matched keys."""

        if self.status == LeadDuplicateStatus.DUPLICATE and not self.matched_fingerprint_keys:
            raise ValueError("duplicate status requires matched fingerprint keys")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe duplicate result payload."""

        return self.model_dump(mode="json")
