from constructionsight.lead_workflow_models import LeadWorkflowStatus


def test_lead_status_enum_available() -> None:
    assert LeadWorkflowStatus.READY.value == "ready"
