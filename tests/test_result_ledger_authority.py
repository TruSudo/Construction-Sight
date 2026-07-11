from __future__ import annotations

from sqlalchemy import inspect, select

import pytest

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_authority_service import (
    ResultLedgerAuthorityError,
    apply_authoritative_result_ledger,
    load_result_ledger_authority,
    load_result_ledger_record,
)
from constructionsight.result_ledger_models import (
    ResultLedgerAuthorityRecord,
    ResultLedgerStatus,
)
from constructionsight.result_ledger_service import build_result_ledger_record
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_result_ledger_record
from constructionsight.storage.result_ledger_authority_orm import (
    ResultLedgerAuthorityEventRow,
    ResultLedgerAuthorityRecordRow,
)
from constructionsight.storage.result_ledger_authority_store import (
    compare_and_swap_result_ledger_authority_record,
)


def _factory(database_url: str = "sqlite:///:memory:"):
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return engine, session_factory(engine)


def _workflow(
    status: LeadWorkflowStatus = LeadWorkflowStatus.CLOSED_SUCCESS,
) -> LeadWorkflowRecord:
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        status=status,
        lead_score=80,
    )


def _won_ledger(
    workflow: LeadWorkflowRecord,
    *,
    gross_value: float = 1000.0,
    reasons: list[str] | None = None,
):
    return build_result_ledger_record(
        workflow=workflow,
        status=ResultLedgerStatus.WON,
        gross_value=gross_value,
        share_rate=0.1,
        reasons=reasons or ["contract won"],
    )


def test_result_authority_tables_are_created() -> None:
    engine, _session_factory = _factory()

    table_names = set(inspect(engine).get_table_names())

    assert "result_ledger_authorities" in table_names
    assert "result_ledger_authority_events" in table_names


def test_result_ledger_identity_is_content_addressed_and_reason_order_stable() -> None:
    workflow = _workflow()
    first = _won_ledger(workflow, reasons=["signed", "verified"])
    reordered = _won_ledger(workflow, reasons=["verified", "signed"])
    changed_value = _won_ledger(workflow, gross_value=1200.0)

    assert first.ledger_id == reordered.ledger_id
    assert first.reasons == ["signed", "verified"]
    assert reordered.reasons == ["signed", "verified"]
    assert first.ledger_id != changed_value.ledger_id


def test_initial_authority_persists_ledger_pointer_and_event() -> None:
    _engine, factory = _factory()
    workflow = _workflow()
    ledger = _won_ledger(workflow)

    with managed_session(factory) as session:
        report = apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=ledger,
            expected_current_ledger_id=None,
            reason="operator confirmed successful outcome",
        )

    with managed_session(factory) as session:
        authority = load_result_ledger_authority(session, workflow.workflow_id)
        stored_ledger = load_result_ledger_record(session, ledger.ledger_id)
        ledger_rows = session.execute(select(ResultLedgerRecordRow)).scalars().all()
        authority_rows = session.execute(
            select(ResultLedgerAuthorityRecordRow)
        ).scalars().all()
        event_rows = session.execute(
            select(ResultLedgerAuthorityEventRow)
        ).scalars().all()

    assert report.authority.revision == 1
    assert report.event.previous_ledger_id is None
    assert authority is not None
    assert authority.current_ledger_id == ledger.ledger_id
    assert stored_ledger.ledger_id == ledger.ledger_id
    assert len(ledger_rows) == 1
    assert len(authority_rows) == 1
    assert len(event_rows) == 1


def test_authority_correction_preserves_both_ledgers_and_event_history() -> None:
    _engine, factory = _factory()
    workflow = _workflow()
    first = _won_ledger(workflow, gross_value=1000.0)
    corrected = _won_ledger(
        workflow,
        gross_value=1200.0,
        reasons=["corrected signed contract value"],
    )

    with managed_session(factory) as session:
        apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=first,
            expected_current_ledger_id=None,
            reason="initial result confirmation",
        )
        report = apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=corrected,
            expected_current_ledger_id=first.ledger_id,
            reason="correct gross contract value",
        )

    with managed_session(factory) as session:
        authority = load_result_ledger_authority(session, workflow.workflow_id)
        ledger_rows = session.execute(
            select(ResultLedgerRecordRow).order_by(ResultLedgerRecordRow.id)
        ).scalars().all()
        event_rows = session.execute(
            select(ResultLedgerAuthorityEventRow).order_by(
                ResultLedgerAuthorityEventRow.revision
            )
        ).scalars().all()

    assert report.authority.revision == 2
    assert report.event.previous_ledger_id == first.ledger_id
    assert authority is not None
    assert authority.current_ledger_id == corrected.ledger_id
    assert authority.revision == 2
    assert [row.ledger_id for row in ledger_rows] == [
        first.ledger_id,
        corrected.ledger_id,
    ]
    assert [row.revision for row in event_rows] == [1, 2]


def test_stale_authority_expectation_rejects_without_new_rows() -> None:
    _engine, factory = _factory()
    workflow = _workflow()
    first = _won_ledger(workflow)
    corrected = _won_ledger(workflow, gross_value=1200.0)

    with managed_session(factory) as session:
        apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=first,
            expected_current_ledger_id=None,
            reason="initial result",
        )

    with managed_session(factory) as session:
        with pytest.raises(ResultLedgerAuthorityError, match="operator expectation"):
            apply_authoritative_result_ledger(
                session,
                workflow=workflow,
                ledger=corrected,
                expected_current_ledger_id="result-ledger:stale",
                reason="stale correction",
            )

    with managed_session(factory) as session:
        ledger_count = len(
            session.execute(select(ResultLedgerRecordRow)).scalars().all()
        )
        event_count = len(
            session.execute(select(ResultLedgerAuthorityEventRow)).scalars().all()
        )

    assert ledger_count == 1
    assert event_count == 1


def test_noop_authority_correction_is_rejected() -> None:
    _engine, factory = _factory()
    workflow = _workflow()
    ledger = _won_ledger(workflow)

    with managed_session(factory) as session:
        apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=ledger,
            expected_current_ledger_id=None,
            reason="initial result",
        )
        with pytest.raises(ResultLedgerAuthorityError, match="different ledger"):
            apply_authoritative_result_ledger(
                session,
                workflow=workflow,
                ledger=ledger,
                expected_current_ledger_id=ledger.ledger_id,
                reason="repeat same result",
            )


def test_atomic_compare_and_swap_rejects_stale_revision() -> None:
    _engine, factory = _factory()
    workflow = _workflow()
    ledger = _won_ledger(workflow)

    with managed_session(factory) as session:
        report = apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=ledger,
            expected_current_ledger_id=None,
            reason="initial result",
        )
        stale_replacement = ResultLedgerAuthorityRecord(
            authority_id=report.authority.authority_id,
            workflow_id=workflow.workflow_id,
            current_ledger_id="result-ledger:replacement",
            revision=2,
        )
        with pytest.raises(ValueError, match="changed after operator review"):
            compare_and_swap_result_ledger_authority_record(
                session,
                stale_replacement,
                expected_current_ledger_id=ledger.ledger_id,
                expected_revision=0,
            )


def test_immutable_ledger_store_rejects_same_id_with_different_content() -> None:
    _engine, factory = _factory()
    workflow = _workflow(LeadWorkflowStatus.CLOSED_NO_FIT)
    ledger = build_result_ledger_record(
        workflow=workflow,
        status=ResultLedgerStatus.LOST,
        reasons=["not selected"],
    )
    collision = ledger.model_copy(update={"reasons": ["different outcome reason"]})

    with managed_session(factory) as session:
        store_result_ledger_record(session, ledger)
        with pytest.raises(ValueError, match="identity collision"):
            store_result_ledger_record(session, collision)


def test_workflow_and_result_status_must_agree() -> None:
    _engine, factory = _factory()
    active_workflow = _workflow(LeadWorkflowStatus.ACTIVE)
    won = _won_ledger(active_workflow)
    successful_workflow = _workflow(LeadWorkflowStatus.CLOSED_SUCCESS)
    lost = build_result_ledger_record(
        workflow=successful_workflow,
        status=ResultLedgerStatus.LOST,
        reasons=["not selected"],
    )

    with managed_session(factory) as session:
        with pytest.raises(ResultLedgerAuthorityError, match="non-final workflow"):
            apply_authoritative_result_ledger(
                session,
                workflow=active_workflow,
                ledger=won,
                expected_current_ledger_id=None,
                reason="invalid early win",
            )
        with pytest.raises(ResultLedgerAuthorityError, match="requires a won"):
            apply_authoritative_result_ledger(
                session,
                workflow=successful_workflow,
                ledger=lost,
                expected_current_ledger_id=None,
                reason="incompatible result",
            )


def test_closed_no_fit_workflow_accepts_lost_authority() -> None:
    _engine, factory = _factory()
    workflow = _workflow(LeadWorkflowStatus.CLOSED_NO_FIT)
    ledger = build_result_ledger_record(
        workflow=workflow,
        status=ResultLedgerStatus.LOST,
        reasons=["not selected"],
    )

    with managed_session(factory) as session:
        report = apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=ledger,
            expected_current_ledger_id=None,
            reason="operator confirmed loss",
        )

    assert report.ledger.status == ResultLedgerStatus.LOST


def test_authority_loader_rejects_indexed_payload_drift() -> None:
    _engine, factory = _factory()
    workflow = _workflow()
    ledger = _won_ledger(workflow)

    with managed_session(factory) as session:
        apply_authoritative_result_ledger(
            session,
            workflow=workflow,
            ledger=ledger,
            expected_current_ledger_id=None,
            reason="initial result",
        )

    with managed_session(factory) as session:
        row = session.execute(select(ResultLedgerAuthorityRecordRow)).scalar_one()
        row.revision = 99

    with managed_session(factory) as session:
        with pytest.raises(ResultLedgerAuthorityError, match="disagree with payload"):
            load_result_ledger_authority(session, workflow.workflow_id)
