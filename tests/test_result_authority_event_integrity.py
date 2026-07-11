import json

import pytest
from sqlalchemy import select

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_authority_service import (
    ResultAuthorityError,
    apply_authoritative_result,
    list_result_authority_events,
)
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_store import store_lead_workflow_record
from constructionsight.storage.result_authority_orm import ResultAuthorityEventRow


def test_authority_event_must_resolve_to_immutable_ledger_revision() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    workflow = LeadWorkflowRecord(
        workflow_id="lead-workflow:event-integrity",
        package_id="lead-review:event-integrity",
        base_candidate_id="candidate:event-integrity",
        status=LeadWorkflowStatus.READY,
        lead_score=80,
    )

    with managed_session(factory) as session:
        store_lead_workflow_record(session, workflow)
        apply_authoritative_result(
            session,
            workflow_id=workflow.workflow_id,
            expected_current_ledger_id=None,
            status=ResultLedgerStatus.UNKNOWN,
            authority_reason="initial result",
        )

    with managed_session(factory) as session:
        row = session.execute(select(ResultAuthorityEventRow)).scalar_one()
        payload = json.loads(row.payload_json)
        payload["current_ledger_id"] = "result-ledger:nonexistent"
        row.current_ledger_id = "result-ledger:nonexistent"
        row.payload_json = json.dumps(payload, sort_keys=True)

    with (
        managed_session(factory) as session,
        pytest.raises(ResultAuthorityError, match="current ledger disagrees"),
    ):
        list_result_authority_events(session, workflow.workflow_id)
