import pytest
from pydantic import ValidationError

from constructionsight.domain_types import ConfidenceBand
from constructionsight.intake_models import FactConfidence
from constructionsight.opportunity_models import (
    OpportunityCandidate,
    OpportunityPriority,
    OpportunityReadiness,
    OpportunityTransitionEvent,
    OpportunityTransitionKind,
)


def test_transition_event_rejects_duplicate_fact_ids() -> None:
    with pytest.raises(ValidationError):
        OpportunityTransitionEvent(
            event_id="transition:abc:001",
            event_kind=OpportunityTransitionKind.PERMIT_ISSUED,
            label="Issued permit signal",
            evidence_id="evidence:abc",
            fact_ids=["fact:abc:001", "fact:abc:001"],
            confidence=FactConfidence.SOURCE_CLAIMED,
            score_delta=30,
            rationale="Issued permits are high-value outreach triggers.",
        )


def test_candidate_rejects_non_hold_priority_without_transition_events() -> None:
    with pytest.raises(ValidationError):
        OpportunityCandidate(
            candidate_id="candidate:abc",
            intake_id="intake:abc",
            evidence_id="evidence:abc",
            source_name="manual note",
            transition_events=[],
            lead_score=50,
            readiness=OpportunityReadiness.RESEARCH_READY,
            priority=OpportunityPriority.MEDIUM,
            confidence_band=ConfidenceBand.MODERATE,
            recommended_action="Research before outreach.",
        )
