"""Lead duplicate suppression models."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

_SPACE_RE = re.compile(r"\\s+")
_NON_WORD_RE = re.compile(r"[^A-Z0-9]+")


def normalize_lead_title_value(value: str) -> str:
    """Return the canonical v2 title normalization used by lead identity."""

    cleaned = _NON_WORD_RE.sub(" ", value.upper())
    return _SPACE_RE.sub(" ", cleaned).strip()


def canonical_lead_fingerprint_key(
    *,
    site_key: str | None,
    source_key: str | None,
    source_record_id: str | None,
    normalized_title: str | None,
) -> str:
    """Return a full-digest v2 lead fingerprint identity."""

    basis = "|".join(
        [site_key or "", source_key or "", source_record_id or "", normalized_title or ""]
    )
    return f"lead-fingerprint:v2:{hashlib.sha256(basis.encode('utf-8')).hexdigest()}"


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
    raw_title: str | None = None
    normalized_title: str | None = None
    lead_score: int = Field(default=0, ge=0, le=100)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def require_canonical_identity(self) -> LeadFingerprint:
        """Recompute normalization and fingerprint identity at the model boundary."""

        expected_title = (
            normalize_lead_title_value(self.raw_title)
            if self.raw_title is not None
            else None
        )
        if self.normalized_title != expected_title:
            raise ValueError("normalized_title does not match canonical raw_title derivation")
        if not any(
            [
                self.site_key,
                self.source_key and self.source_record_id,
                self.normalized_title,
            ]
        ):
            raise ValueError("lead fingerprint requires site, source record, or title basis")
        expected_key = canonical_lead_fingerprint_key(
            site_key=self.site_key,
            source_key=self.source_key,
            source_record_id=self.source_record_id,
            normalized_title=self.normalized_title,
        )
        if self.fingerprint_key != expected_key:
            raise ValueError("fingerprint_key does not match canonical fingerprint content")
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
