"""Government decision record models."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.domain_types import ConfidenceBand, confidence_band


class DecisionSourceKind(StrEnum):
    """Source family for a government decision signal."""

    CEQA = "ceqa"
    AGENDA = "agenda"
    STAFF_REPORT = "staff_report"
    PLANNING_COMMISSION = "planning_commission"
    CITY_COUNCIL = "city_council"
    SHOVELS_STYLE = "shovels_style"
    USER_PROVIDED = "user_provided"
    UNKNOWN = "unknown"


class DecisionKind(StrEnum):
    """Normalized decision or hearing kind."""

    APPROVAL = "approval"
    HEARING = "hearing"
    ZONING_CHANGE = "zoning_change"
    ENVIRONMENTAL_NOTICE = "environmental_notice"
    ENTITLEMENT = "entitlement"
    PROJECT_DISCUSSION = "project_discussion"
    UNKNOWN = "unknown"


class DecisionRecord(BaseModel):
    """Provider-neutral government decision or pre-permit signal."""

    decision_key: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    source_record_id: str | None = None
    source_kind: DecisionSourceKind = DecisionSourceKind.UNKNOWN
    decision_kind: DecisionKind = DecisionKind.UNKNOWN
    title: str = Field(min_length=1)
    normalized_title: str = Field(min_length=1)
    decision_date: date | None = None
    effective_date: date | None = None
    jurisdiction: str | None = None
    county: str | None = None
    case_number: str | None = None
    project_name: str | None = None
    site_key: str | None = None
    apn: str | None = None
    applicant_name: str | None = None
    developer_name: str | None = None
    contractor_key: str | None = None
    project_value: float | None = Field(default=None, ge=0)
    unit_count: int | None = Field(default=None, ge=0)
    source_url: str | None = None
    summary: str | None = None
    why_it_matters: str | None = None
    confidence_score: int = Field(default=0, ge=0, le=100)
    confidence_band: ConfidenceBand = ConfidenceBand.UNKNOWN
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate reasons or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("decision record text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_confidence_consistency(self) -> DecisionRecord:
        """Require confidence band to match score."""

        expected = confidence_band(self.confidence_score)
        if self.confidence_band != expected:
            raise ValueError("confidence_band must match confidence_score")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe decision payload."""

        return self.model_dump(mode="json")


class DecisionMatchStatus(StrEnum):
    """Decision-to-site match status."""

    MATCHED = "matched"
    REVIEW_NEEDED = "review_needed"
    UNMATCHED = "unmatched"


class DecisionSiteMatch(BaseModel):
    """Candidate link between a decision and a site or parcel."""

    decision_key: str = Field(min_length=1)
    site_key: str | None = None
    apn: str | None = None
    status: DecisionMatchStatus
    confidence_score: int = Field(default=0, ge=0, le=100)
    confidence_band: ConfidenceBand = ConfidenceBand.UNKNOWN
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @field_validator("reasons", "limitations")
    @classmethod
    def require_unique_text_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate reasons or limitations."""

        if len(values) != len(set(values)):
            raise ValueError("decision match text lists must contain unique values")
        return values

    @model_validator(mode="after")
    def require_match_consistency(self) -> DecisionSiteMatch:
        """Require confidence and site data to align with match status."""

        expected = confidence_band(self.confidence_score)
        if self.confidence_band != expected:
            raise ValueError("confidence_band must match confidence_score")
        if self.status == DecisionMatchStatus.MATCHED and self.site_key is None:
            raise ValueError("matched decision-site links require site_key")
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe decision-site match payload."""

        return self.model_dump(mode="json")
