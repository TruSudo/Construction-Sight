import pytest

from constructionsight.lead_review_models import LeadReviewItem, LeadReviewPackage, LeadReviewStatus
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_rules import (
    FINAL_LEAD_WORKFLOW_STATUSES,
    LEAD_WORKFLOW_TRANSITION_RULES,
    validate_lead_workflow_transition,
)
from constructionsight.lead_workflow_service import create_lead_workflow, transition_lead_workflow


def _ready_package() -> LeadReviewPackage:
    return LeadReviewPackage(
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        lead_score=80,
        status=LeadReviewStatus.READY,
        summary="test package",
        items=[
            LeadReviewItem(
                item_key="lead-item:test",
                label="review package",
                rationale="test rationale",
            )
        ],
    )


def _monitor_package() -> LeadReviewPackage:
    return LeadReviewPackage(
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        lead_score=20,
        status=LeadReviewStatus.MONITOR,
        summary="test package",
    )


def test_lead_status_matrix_contains_all_statuses() -> None:
    assert set(LEAD_WORKFLOW_TRANSITION_RULES) == set(LeadWorkflowStatus)
    assert FINAL_LEAD_WORKFLOW_STATUSES == {
        LeadWorkflowStatus.CLOSED_SUCCESS,
        LeadWorkflowStatus.CLOSED_NO_FIT,
    }


def test_lead_status_matrix_allows_configured_moves() -> None:
    validate_lead_workflow_transition(
        LeadWorkflowStatus.READY,
        LeadWorkflowStatus.ACTIVE,
    )
    validate_lead_workflow_transition(
        LeadWorkflowStatus.ACTIVE,
        LeadWorkflowStatus.CLOSED_SUCCESS,
    )


def test_lead_status_matrix_rejects_unlisted_move() -> None:
    record = create_lead_workflow(package=_monitor_package())

    with pytest.raises(ValueError, match="not allowed"):
        transition_lead_workflow(
            record=record,
            next_status=LeadWorkflowStatus.CLOSED_SUCCESS,
            reason="unlisted move",
        )


def test_lead_status_matrix_final_status_has_no_outgoing_move() -> None:
    record = create_lead_workflow(package=_ready_package())
    active = transition_lead_workflow(
        record=record,
        next_status=LeadWorkflowStatus.ACTIVE,
        reason="accepted",
    )
    final = transition_lead_workflow(
        record=active,
        next_status=LeadWorkflowStatus.CLOSED_SUCCESS,
        reason="complete",
    )

    with pytest.raises(ValueError, match="final lead workflow status"):
        transition_lead_workflow(
            record=final,
            next_status=LeadWorkflowStatus.ACTIVE,
            reason="unlisted final move",
        )
