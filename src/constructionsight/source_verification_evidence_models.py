"""Source verification evidence package models."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RedirectClassification(StrEnum):
    """Redirect classification for source verification evidence."""

    NOT_CHECKED = "not_checked"
    NO_REDIRECT = "no_redirect"
    SAME_HOST_REDIRECT = "same_host_redirect"
    CROSS_HOST_REDIRECT = "cross_host_redirect"
    DOWNGRADED_TO_HTTP = "downgraded_to_http"
    UNKNOWN = "unknown"


class SourcePromotionRecommendation(StrEnum):
    """Dry-run registry-promotion recommendation."""

    KEEP_SEED_ONLY = "keep_seed_only"
    KEEP_UNVERIFIED_REACHABLE = "keep_unverified_reachable"
    MARK_BLOCKED_CANDIDATE = "mark_blocked_candidate"
    MARK_FAILED_CANDIDATE = "mark_failed_candidate"
    MARK_PARTIAL_CANDIDATE = "mark_partial_candidate"
    VERIFIED_CANDIDATE_REVIEW = "verified_candidate_review"


class PublicQueryEvidenceStatus(StrEnum):
    """Status for public query/search/list/detail evidence."""

    NOT_CHECKED = "not_checked"
    ADAPTER_CONTRACT_READY = "adapter_contract_ready"
    UNKNOWN_NEEDS_MANUAL_REVIEW = "unknown_needs_manual_review"
    PLACEHOLDER_ADAPTER = "placeholder_adapter"


class SourceVerificationEvidenceRow(BaseModel):
    """Evidence row for one source verification review."""

    source_key: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    platform_family: str = Field(min_length=1)
    original_url: str = Field(min_length=1)
    final_url: str | None = None
    http_status_code: int | None = Field(default=None, ge=100, le=599)
    http_checked: bool
    redirect_classification: RedirectClassification
    verification_status: str = Field(min_length=1)
    adapter_status: str = Field(min_length=1)
    readiness_status: str = Field(min_length=1)
    lawful_access_boundary: str = Field(min_length=1)
    public_query_evidence_status: PublicQueryEvidenceStatus
    operator_review_required: bool
    recommendation: SourcePromotionRecommendation
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    next_action: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate reasons or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("evidence row text lists must contain unique values")
        return values


class SourceVerificationEvidencePackage(BaseModel):
    """Aggregated source verification evidence package."""

    source_count: int = Field(ge=0)
    recommendation_counts: dict[str, int] = Field(default_factory=dict)
    redirect_counts: dict[str, int] = Field(default_factory=dict)
    rows: list[SourceVerificationEvidenceRow] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_rows(
        cls,
        rows: list[SourceVerificationEvidenceRow],
    ) -> SourceVerificationEvidencePackage:
        """Build package summary counts from rows."""

        return cls(
            source_count=len(rows),
            recommendation_counts=dict(Counter(row.recommendation.value for row in rows)),
            redirect_counts=dict(Counter(row.redirect_classification.value for row in rows)),
            rows=rows,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe evidence package payload."""

        return self.model_dump(mode="json")
