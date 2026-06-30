import pytest
from pydantic import ValidationError

from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)


def test_workflow_record_requires_latest_event_to_match_status() -> None:
    event = LeadWorkflowEvent(
        event_id="lead-workflow-event:test",
        current_status=LeadWorkflowStatus.MONITOR,
        reason="created",
    )

    with pytest.raises(ValidationError):
        LeadWorkflowRecord(
            workflow_id="lead-workflow:test",
            package_id="lead-review:test",
            base_candidate_id="candidate:test",
            status=LeadWorkflowStatus.READY,
            lead_score=80,
            events=[event],
        )


def test_workflow_record_rejects_duplicate_notes() -> None:
    with pytest.raises(ValidationError):
        LeadWorkflowRecord(
            workflow_id="lead-workflow:test",
            package_id="lead-review:test",
            base_candidate_id="candidate:test",
            status=LeadWorkflowStatus.MONITOR,
            lead_score=20,
            notes=["x", "x"],
        )


def test_workflow_record_serializes() -> None:
    event = LeadWorkflowEvent(
        event_id="lead-workflow-event:test",
        current_status=LeadWorkflowStatus.READY,
        reason="created",
    )
    record = LeadWorkflowRecord(
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        status=LeadWorkflowStatus.READY,
        lead_score=80,
        events=[event],
    )

    assert record.to_dict()["status"] == "ready"
