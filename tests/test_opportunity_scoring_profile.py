import pytest
from pydantic import ValidationError

from constructionsight.opportunity_scoring_profile import (
    DEFAULT_OPPORTUNITY_SCORING_PROFILE,
    OpportunityScoringProfile,
)
from constructionsight.permit_transition_models import PermitTransitionKind
from constructionsight.site_resolution_models import SiteResolutionStatus


def test_default_opportunity_scoring_profile_preserves_current_weights() -> None:
    profile = DEFAULT_OPPORTUNITY_SCORING_PROFILE

    assert profile.profile_key == "opportunity-scoring:default"
    assert profile.version == "2026-06-30.1"
    assert profile.site_score(SiteResolutionStatus.RESOLVED) == 20
    assert profile.site_score(SiteResolutionStatus.PARTIAL) == 10
    assert profile.site_score(SiteResolutionStatus.AMBIGUOUS) == 10
    assert profile.site_score(SiteResolutionStatus.UNRESOLVED) is None
    assert profile.permit_transition_scores[PermitTransitionKind.STATUS_CHANGED] == 20
    assert profile.contractor_with_license_score == 15
    assert profile.contractor_without_license_score == 8
    assert profile.decision_with_site_score == 15
    assert profile.decision_without_site_score == 10


def test_scoring_profile_requires_complete_permit_transition_scores() -> None:
    with pytest.raises(ValidationError, match="missing permit transition scores"):
        OpportunityScoringProfile(
            profile_key="profile:test",
            version="1",
            site_resolved_score=20,
            site_partial_score=10,
            permit_transition_scores={PermitTransitionKind.NEW_RECORD: 10},
            contractor_with_license_score=15,
            contractor_without_license_score=8,
            decision_with_site_score=15,
            decision_without_site_score=10,
            high_value_threshold=70,
            review_threshold=50,
            monitor_threshold=1,
        )


def test_scoring_profile_requires_descending_thresholds() -> None:
    with pytest.raises(ValidationError, match="thresholds must descend"):
        OpportunityScoringProfile(
            profile_key="profile:test",
            version="1",
            site_resolved_score=20,
            site_partial_score=10,
            permit_transition_scores={kind: 10 for kind in PermitTransitionKind},
            contractor_with_license_score=15,
            contractor_without_license_score=8,
            decision_with_site_score=15,
            decision_without_site_score=10,
            high_value_threshold=40,
            review_threshold=50,
            monitor_threshold=1,
        )
