import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.result_ledger_service import (
    build_result_ledger_record,
    supersede_result_ledger_record,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_result_ledger_record


def _factory() -> sessionmaker[Session]:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return session_factory(engine)


def _workflow() -> LeadWorkflowRecord:
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:supersession",
        package_id="lead-review:supersession",
        base_candidate_id="candidate:supersession",
        status=LeadWorkflowStatus.READY,
        lead_score=90,
    )


def test_store_result_ledger_record_appends_superseding_revision() -> None:
    original = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.UNKNOWN,
    )
    corrected = supersede_result_ledger_record(
        current=original,
        status=ResultLedgerStatus.WON,
        correction_reason="award documentation received",
        gross_value=5000.0,
        share_rate=0.1,
    )

    with managed_session(_factory()) as session:
        store_result_ledger_record(session, original)
        store_result_ledger_record(session, corrected)
        session.flush()
        rows = session.execute(
            select(ResultLedgerRecordRow).order_by(ResultLedgerRecordRow.id)
        ).scalars().all()

        assert len(rows) == 2
        assert json.loads(rows[0].payload_json)["revision"] == 1
        assert json.loads(rows[1].payload_json)["revision"] == 2
        assert json.loads(rows[1].payload_json)["supersedes_ledger_id"] == original.ledger_id


def test_store_result_ledger_record_rejects_immutable_payload_rewrite() -> None:
    original = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.UNKNOWN,
    )
    tampered = original.model_copy(update={"reasons": ["changed after persistence"]})

    with managed_session(_factory()) as session:
        store_result_ledger_record(session, original)
        session.flush()
        with pytest.raises(ValueError, match="immutable"):
            store_result_ledger_record(session, tampered)


def test_store_result_ledger_record_rejects_noncontiguous_append() -> None:
    original = build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.UNKNOWN,
    )
    corrected = supersede_result_ledger_record(
        current=original,
        status=ResultLedgerStatus.LOST,
        correction_reason="confirmed loss",
    )
    gapped = corrected.model_copy(update={"revision": 3})

    with managed_session(_factory()) as session:
        store_result_ledger_record(session, original)
        session.flush()
        with pytest.raises(ValueError, match="contiguous from one"):
            store_result_ledger_record(session, gapped)
