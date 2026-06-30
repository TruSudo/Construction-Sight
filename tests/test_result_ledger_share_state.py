import json

from sqlalchemy import select

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_models import ResultLedgerStatus, ResultShareStatus
from constructionsight.result_ledger_service import build_result_ledger_record
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_result_ledger_record


def _session_factory():
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return engine, session_factory(engine)


def _workflow() -> LeadWorkflowRecord:
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        status=LeadWorkflowStatus.READY,
        lead_score=80,
    )


def test_result_ledger_persists_pending_share_rate_state() -> None:
    _engine, factory = _session_factory()
    ledger = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=1000.0,
    )

    with managed_session(factory) as session:
        store_result_ledger_record(session, ledger)
        session.flush()
        row = session.execute(select(ResultLedgerRecordRow)).scalar_one()

        assert ledger.share_status == ResultShareStatus.PENDING_SHARE_RATE
        assert row.share_status == "pending_share_rate"
        payload = json.loads(row.payload_json)
        assert payload["share_status"] == "pending_share_rate"
        assert payload["limitations"] == ["share rate is missing"]
