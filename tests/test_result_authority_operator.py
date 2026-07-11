import json

import pytest
from sqlalchemy import inspect, select
from typer.testing import CliRunner

from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)
from constructionsight.result_authority_cli import app
from constructionsight.result_authority_service import (
    ResultAuthorityError,
    apply_authoritative_result,
    list_result_authority_events,
    load_result_authority_snapshot,
)
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_lead_workflow_record
from constructionsight.storage.result_authority_orm import (
    ResultAuthorityEventRow,
    ResultAuthorityHeadRow,
)


def _database_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'result-authority.sqlite3'}"


def _factory(database_url: str):
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return engine, session_factory(engine)


def _workflow() -> LeadWorkflowRecord:
    status = LeadWorkflowStatus.READY
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:result-authority",
        package_id="lead-review:result-authority",
        base_candidate_id="candidate:result-authority",
        status=status,
        lead_score=88,
        events=[
            LeadWorkflowEvent(
                event_id="lead-workflow-event:result-authority",
                current_status=status,
                reason="result authority fixture",
            )
        ],
    )


def _seed_workflow(database_url: str) -> None:
    _engine, factory = _factory(database_url)
    with managed_session(factory) as session:
        store_lead_workflow_record(session, _workflow())


def test_result_authority_tables_are_created(tmp_path) -> None:
    engine, _factory_value = _factory(_database_url(tmp_path))

    table_names = set(inspect(engine).get_table_names())

    assert "result_authority_heads" in table_names
    assert "result_authority_events" in table_names


def test_initial_result_persists_head_event_and_ledger(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_workflow(database_url)
    _engine, factory = _factory(database_url)

    with managed_session(factory) as session:
        report = apply_authoritative_result(
            session,
            workflow_id=_workflow().workflow_id,
            expected_current_ledger_id=None,
            status=ResultLedgerStatus.UNKNOWN,
            authority_reason="operator recorded initial unknown outcome",
            outcome_reasons=["award status not yet confirmed"],
        )

    with managed_session(factory) as session:
        snapshot = load_result_authority_snapshot(session, _workflow().workflow_id)
        events = list_result_authority_events(session, _workflow().workflow_id)
        ledger_rows = session.execute(select(ResultLedgerRecordRow)).scalars().all()
        head_rows = session.execute(select(ResultAuthorityHeadRow)).scalars().all()
        event_rows = session.execute(select(ResultAuthorityEventRow)).scalars().all()

    assert report.current.revision == 1
    assert report.previous_ledger_id is None
    assert snapshot is not None
    assert snapshot.current.ledger_id == report.current.ledger_id
    assert snapshot.head is not None
    assert snapshot.head.current_ledger_id == report.current.ledger_id
    assert len(events) == 1
    assert events[0].reason == "operator recorded initial unknown outcome"
    assert len(ledger_rows) == 1
    assert len(head_rows) == 1
    assert len(event_rows) == 1


def test_result_correction_preserves_history_and_moves_head(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_workflow(database_url)
    _engine, factory = _factory(database_url)

    with managed_session(factory) as session:
        initial = apply_authoritative_result(
            session,
            workflow_id=_workflow().workflow_id,
            expected_current_ledger_id=None,
            status=ResultLedgerStatus.UNKNOWN,
            authority_reason="initial result",
        )
        corrected = apply_authoritative_result(
            session,
            workflow_id=_workflow().workflow_id,
            expected_current_ledger_id=initial.current.ledger_id,
            status=ResultLedgerStatus.WON,
            authority_reason="signed award documentation received",
            decided_date=None,
            gross_value=12500.0,
            share_rate=0.075,
            outcome_reasons=["signed contract received"],
        )

    with managed_session(factory) as session:
        snapshot = load_result_authority_snapshot(session, _workflow().workflow_id)
        events = list_result_authority_events(session, _workflow().workflow_id)

    assert snapshot is not None
    assert corrected.current.revision == 2
    assert corrected.current.supersedes_ledger_id == initial.current.ledger_id
    assert snapshot.current.ledger_id == corrected.current.ledger_id
    assert [ledger.revision for ledger in snapshot.history] == [1, 2]
    assert [event.revision for event in events] == [1, 2]
    assert snapshot.history[0].status == ResultLedgerStatus.UNKNOWN
    assert snapshot.history[1].status == ResultLedgerStatus.WON
    assert snapshot.history[1].share is not None
    assert snapshot.history[1].share.share_value == 937.5


def test_stale_result_expectation_rejects_without_partial_rows(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_workflow(database_url)
    _engine, factory = _factory(database_url)

    with managed_session(factory) as session:
        initial = apply_authoritative_result(
            session,
            workflow_id=_workflow().workflow_id,
            expected_current_ledger_id=None,
            status=ResultLedgerStatus.UNKNOWN,
            authority_reason="initial result",
        )

    with (
        managed_session(factory) as session,
        pytest.raises(ResultAuthorityError, match="operator expectation"),
    ):
        apply_authoritative_result(
            session,
            workflow_id=_workflow().workflow_id,
            expected_current_ledger_id="result-ledger:stale",
            status=ResultLedgerStatus.LOST,
            authority_reason="stale correction",
            outcome_reasons=["not selected"],
        )

    with managed_session(factory) as session:
        snapshot = load_result_authority_snapshot(session, _workflow().workflow_id)
        events = list_result_authority_events(session, _workflow().workflow_id)
        ledger_rows = session.execute(select(ResultLedgerRecordRow)).scalars().all()

    assert snapshot is not None
    assert snapshot.current.ledger_id == initial.current.ledger_id
    assert len(snapshot.history) == 1
    assert len(events) == 1
    assert len(ledger_rows) == 1


def test_noop_result_correction_is_rejected(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_workflow(database_url)
    _engine, factory = _factory(database_url)

    with managed_session(factory) as session:
        initial = apply_authoritative_result(
            session,
            workflow_id=_workflow().workflow_id,
            expected_current_ledger_id=None,
            status=ResultLedgerStatus.LOST,
            authority_reason="initial loss",
            outcome_reasons=["not selected"],
        )
        with pytest.raises(ResultAuthorityError, match="must change"):
            apply_authoritative_result(
                session,
                workflow_id=_workflow().workflow_id,
                expected_current_ledger_id=initial.current.ledger_id,
                status=ResultLedgerStatus.LOST,
                authority_reason="duplicate loss entry",
                outcome_reasons=["not selected"],
            )


def test_result_authority_loader_rejects_head_payload_drift(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_workflow(database_url)
    _engine, factory = _factory(database_url)

    with managed_session(factory) as session:
        apply_authoritative_result(
            session,
            workflow_id=_workflow().workflow_id,
            expected_current_ledger_id=None,
            status=ResultLedgerStatus.UNKNOWN,
            authority_reason="initial result",
        )

    with managed_session(factory) as session:
        row = session.execute(select(ResultAuthorityHeadRow)).scalar_one()
        row.current_revision = 99

    with (
        managed_session(factory) as session,
        pytest.raises(ResultAuthorityError, match="indexed fields disagree"),
    ):
        load_result_authority_snapshot(session, _workflow().workflow_id)


def test_result_cli_requires_explicit_apply(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_workflow(database_url)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "record",
            _workflow().workflow_id,
            "unknown",
            "--expected-current-ledger-id",
            "none",
            "--reason",
            "initial result",
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 2
    assert "Explicit --apply authorization is required." in result.stderr


def test_result_cli_records_corrects_and_lists_history(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed_workflow(database_url)
    runner = CliRunner()

    initial_result = runner.invoke(
        app,
        [
            "record",
            _workflow().workflow_id,
            "unknown",
            "--expected-current-ledger-id",
            "none",
            "--reason",
            "initial result",
            "--outcome-reason",
            "award status pending",
            "--database-url",
            database_url,
            "--apply",
            "--json-output",
        ],
    )

    assert initial_result.exit_code == 0
    initial_payload = json.loads(initial_result.stdout)
    initial_ledger_id = initial_payload["current"]["ledger_id"]

    correction_result = runner.invoke(
        app,
        [
            "record",
            _workflow().workflow_id,
            "won",
            "--expected-current-ledger-id",
            initial_ledger_id,
            "--reason",
            "signed award received",
            "--gross-value",
            "10000.00",
            "--share-rate",
            "0.1",
            "--outcome-reason",
            "signed contract received",
            "--database-url",
            database_url,
            "--apply",
            "--json-output",
        ],
    )

    assert correction_result.exit_code == 0
    correction_payload = json.loads(correction_result.stdout)
    assert correction_payload["current"]["revision"] == 2
    assert correction_payload["current"]["share"]["share_value"] == 1000.0

    history_result = runner.invoke(
        app,
        [
            "history",
            _workflow().workflow_id,
            "--database-url",
            database_url,
            "--json-output",
        ],
    )

    assert history_result.exit_code == 0
    history_payload = json.loads(history_result.stdout)
    assert len(history_payload["snapshot"]["history"]) == 2
    assert len(history_payload["authority_events"]) == 2
    assert history_payload["snapshot"]["current"]["status"] == "won"
