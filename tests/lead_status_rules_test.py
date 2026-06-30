from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_rules import LEAD_WORKFLOW_TRANSITION_RULES


def test_lead_status_rules_cover_all_statuses() -> None:
    assert set(LEAD_WORKFLOW_TRANSITION_RULES) == set(LeadWorkflowStatus)


def test_lead_status_ready_can_become_active() -> None:
    assert LeadWorkflowStatus.ACTIVE in LEAD_WORKFLOW_TRANSITION_RULES[LeadWorkflowStatus.READY]
