"""Versioned opportunity scoring profiles."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator

from constructionsight.permit_transition_models import PermitTransitionKind
from constructionsight.site_resolution_models import SiteResolutionStatus


class OpportunityScoringProfile(BaseModel):
    """Versioned scoring profile for opportunity enrichment."""

    profile_key: str = Field(min_length=1)
    version: str = Field(min_length=1)
    site_resolved_score: int = Field(ge=0, le=100)
    site_partial_score: int = Field(ge=0, le=100)
    permit_transition_scores: dict[PermitTransitionKind, int]
    contractor_with_license_score: int = Field(ge=0, le=100)
    contractor_without_license_score: int = Field(ge=0, le=100)
    decision_with_site_score: int = Field(ge=0, le=100)
    decision_without_site_score: int = Field(ge=0, le=100)
    high_value_threshold: int = Field(ge=0, le=100)
    review_threshold: int = Field(ge=0, le=100)
    monitor_threshold: int = Field(ge=0, le=100)

    @field_validator("permit_transition_scores")
    @classmethod
    def require_complete_permit_transition_scores(
        cls,
        values: dict[PermitTransitionKind, int],
    ) -> dict[PermitTransitionKind, int]:
        """Require a score for every permit transition kind."""

        missing = set(PermitTransitionKind) - set(values)
        if missing:
            missing_values = ", ".join(sorted(kind.value for kind in missing))
            raise ValueError(f"missing permit transition scores: {missing_values}")
        for score in values.values():
            if score < 0 or score > 100:
                raise ValueError("permit transition scores must be between 0 and 100")
        return values

    @model_validator(mode="after")
    def require_threshold_order(self) -> OpportunityScoringProfile:
        """Require thresholds to descend from high-value to monitor."""

        if not (self.high_value_threshold >= self.review_threshold >= self.monitor_threshold >= 0):
            raise ValueError("thresholds must descend: high_value >= review >= monitor >= 0")
        return self

    def site_score(self, status: SiteResolutionStatus) -> int | None:
        """Return configured score for a site-resolution status."""

        if status == SiteResolutionStatus.UNRESOLVED:
            return None
        if status == SiteResolutionStatus.RESOLVED:
            return self.site_resolved_score
        return self.site_partial_score


DEFAULT_OPPORTUNITY_SCORING_PROFILE = OpportunityScoringProfile(
    profile_key="opportunity-scoring:default",
    version="2026-06-30.1",
    site_resolved_score=20,
    site_partial_score=10,
    permit_transition_scores={
        PermitTransitionKind.NEW_RECORD: 10,
        PermitTransitionKind.STATUS_CHANGED: 20,
        PermitTransitionKind.VALUE_CHANGED: 15,
        PermitTransitionKind.CONTRACTOR_CHANGED: 15,
        PermitTransitionKind.DATE_CHANGED: 10,
        PermitTransitionKind.SITE_CHANGED: 20,
        PermitTransitionKind.DESCRIPTION_CHANGED: 5,
    },
    contractor_with_license_score=15,
    contractor_without_license_score=8,
    decision_with_site_score=15,
    decision_without_site_score=10,
    high_value_threshold=70,
    review_threshold=50,
    monitor_threshold=1,
)
