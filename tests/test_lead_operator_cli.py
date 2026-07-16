import json

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from constructionsight.lead_operator_cli import app
from constructionsight.lead_operator_models import LeadOperatorRecordKind
from constructionsight.lead_operator_service import (
    LeadOperatorError,
    get_lead_operator_record,
    list_lead_operator_records,
    load_persisted_lead_workflow,
    transition_persisted_lead_workflow,
)
from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)
from constructionsight.result_ledger_models import ResultLedgerRecord, ResultLedgerStatus
from constructionsight.result_ledger_service import build_result_ledger_record
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import (
    LeadWorkflowEventRecord,
    LeadWorkflowRecordRow,
)
from constructionsight.storage.lead_workflow_store import (
    store_lead_workflow_record,
    store_result_ledger_record,
)


def _database_url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'lead-operator.sqlite3'}"


def _workflow(status: LeadWorkflowStatus = LeadWorkflowStatus.MONITOR) -> LeadWorkflowRecord:
    event = LeadWorkflowEvent(
        event_id="lead-workflow-event:initial",
        current_status=status,
        reason="initial operator workflow state",
    )
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        fingerprint_key="lead-fingerprint:test",
        status=status,
        lead_score=72,
        events=[event],
        notes=["operator-visible note"],
        limitations=["source verification remains pending"],
    )


def _ledger() -> ResultLedgerRecord:
    return build_result_ledger_record(
        workflow=_workflow(),
        status=ResultLedgerStatus.WON,
        gross_value=2500.0,
        reasons=["operator confirmed contract result"],
    )


def _factory(database_url: str):
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return session_factory(engine)


def _seed(database_url: str) -> None:
    factory = _factory(database_url)
    with managed_session(factory) as session:
        store_lead_workflow_record(session, _workflow())
        store_result_ledger_record(session, _ledger())


def test_list_and_detail_preserve_workflow_payload(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        records = list_lead_operator_records(
            session,
            LeadOperatorRecordKind.WORKFLOW,
            status="monitor",
            base_candidate_id="candidate:test",
        )
        detail = get_lead_operator_record(
            session,
            LeadOperatorRecordKind.WORKFLOW,
            "lead-workflow:test",
        )

    assert len(records) == 1
    assert records[0].record_id == "lead-workflow:test"
    assert detail is not None
    assert detail.payload["notes"] == ["operator-visible note"]
    assert detail.payload["limitations"] == ["source verification remains pending"]


def test_list_rejects_unsupported_filter(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    factory = _factory(database_url)

    with (
        managed_session(factory) as session,
        pytest.raises(LeadOperatorError, match="unsupported filter"),
    ):
        list_lead_operator_records(
            session,
            LeadOperatorRecordKind.SHARE,
            status="calculated",
        )


def test_load_rejects_indexed_payload_drift(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        row = session.execute(select(LeadWorkflowRecordRow)).scalar_one()
        row.status = "review"

    with (
        managed_session(factory) as session,
        pytest.raises(LeadOperatorError, match="disagree with payload"),
    ):
        load_persisted_lead_workflow(session, "lead-workflow:test")


def test_transition_rejects_stale_operator_expectation(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with (
        managed_session(factory) as session,
        pytest.raises(LeadOperatorError, match="operator expectation"),
    ):
        transition_persisted_lead_workflow(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.REVIEW,
            next_status=LeadWorkflowStatus.READY,
            reason="review completed",
        )


def test_transition_persists_status_and_event(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        report = transition_persisted_lead_workflow(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="new evidence requires review",
        )

    with managed_session(factory) as session:
        workflow = load_persisted_lead_workflow(session, "lead-workflow:test")
        events = (
            session.execute(
                select(LeadWorkflowEventRecord).where(
                    LeadWorkflowEventRecord.workflow_id == "lead-workflow:test"
                )
            )
            .scalars()
            .all()
        )

    assert report.previous_status == "monitor"
    assert report.current_status == "review"
    assert workflow.status == LeadWorkflowStatus.REVIEW
    assert len(workflow.events) == 2
    assert len(events) == 2


def test_repeated_transition_cycle_persists_distinct_events(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    factory = _factory(database_url)

    with managed_session(factory) as session:
        transition_persisted_lead_workflow(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="review recurring evidence",
        )
        transition_persisted_lead_workflow(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.REVIEW,
            next_status=LeadWorkflowStatus.MONITOR,
            reason="continue monitoring",
        )
        transition_persisted_lead_workflow(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="review recurring evidence",
        )

    with managed_session(factory) as session:
        workflow = load_persisted_lead_workflow(session, "lead-workflow:test")
        rows = (
            session.execute(
                select(LeadWorkflowEventRecord).where(
                    LeadWorkflowEventRecord.workflow_id == "lead-workflow:test"
                )
            )
            .scalars()
            .all()
        )

    event_ids = [event.event_id for event in workflow.events]
    assert len(workflow.events) == 4
    assert len(set(event_ids)) == 4
    assert len(rows) == 4


def test_list_cli_outputs_machine_readable_ledger_payload(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "list",
            "ledger",
            "--database-url",
            database_url,
            "--workflow-id",
            "lead-workflow:test",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["record_id"] == _ledger().ledger_id
    assert payload[0]["payload"]["share_status"] == "pending_share_rate"
    assert payload[0]["payload"]["limitations"] == ["share rate is missing"]


def test_detail_cli_reports_missing_record(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "detail",
            "workflow",
            "lead-workflow:missing",
            "--database-url",
            database_url,
            "--json-output",
        ],
    )

    assert result.exit_code == 2
    assert "workflow record not found: lead-workflow:missing" in result.stderr


def test_transition_cli_requires_explicit_apply(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "transition",
            "lead-workflow:test",
            "review",
            "--expected-current-status",
            "monitor",
            "--reason",
            "new evidence requires review",
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 2
    assert "Explicit --apply authorization is required" in result.stderr


def test_transition_cli_applies_governed_status_change(tmp_path) -> None:
    database_url = _database_url(tmp_path)
    _seed(database_url)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "transition",
            "lead-workflow:test",
            "review",
            "--expected-current-status",
            "monitor",
            "--reason",
            "new evidence requires review",
            "--database-url",
            database_url,
            "--apply",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["previous_status"] == "monitor"
    assert payload["current_status"] == "review"
    assert payload["event_count"] == 2
