from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

import constructionsight.operator_services.lead_workflow_transition_service as transition_service
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.lead_operator_models import LeadWorkflowTransitionReport
from constructionsight.lead_operator_service import LeadOperatorError
from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)
from constructionsight.operator_services.lead_workflow_transition_service import (
    apply_authorized_lead_workflow_transition,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.effect_consumption_store import (
    EffectOutcomeUnavailableError,
)
from constructionsight.storage.lead_workflow_store import store_lead_workflow_record


def _workflow() -> LeadWorkflowRecord:
    return LeadWorkflowRecord(
        workflow_id="lead-workflow:test",
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        fingerprint_key="lead-fingerprint:test",
        status=LeadWorkflowStatus.MONITOR,
        lead_score=72,
        events=[
            LeadWorkflowEvent(
                event_id="lead-workflow-event:initial",
                current_status=LeadWorkflowStatus.MONITOR,
                reason="initial state",
            )
        ],
    )


def _factory(database_url: str = "sqlite+pysqlite:///:memory:"):
    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        store_lead_workflow_record(session, _workflow())
    return factory


class _Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def __call__(
        self,
        session,
        *,
        workflow_id,
        expected_current_status,
        next_status,
        reason,
    ) -> LeadWorkflowTransitionReport:
        del session, expected_current_status
        self.calls.append((workflow_id, next_status.value, reason))
        return LeadWorkflowTransitionReport(
            workflow_id=workflow_id,
            previous_status="monitor",
            current_status=next_status.value,
            event_id="lead-workflow-event:authorized",
            reason=reason,
            event_count=2,
            workflow_payload={},
        )


def test_transition_requires_scope_bound_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    executor = _Executor()
    monkeypatch.setattr(
        transition_service,
        "transition_persisted_lead_workflow",
        executor,
    )

    with (
        managed_session(factory) as session,
        pytest.raises(AuthorizationDeniedError, match="in addition"),
    ):
        apply_authorized_lead_workflow_transition(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="review new evidence",
            caller_confirmation=False,
            operator_id="operator:tyler",
        )

    assert executor.calls == []


def test_transition_rejects_stale_state_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    executor = _Executor()
    monkeypatch.setattr(
        transition_service,
        "transition_persisted_lead_workflow",
        executor,
    )

    with (
        managed_session(factory) as session,
        pytest.raises(LeadOperatorError, match="operator expectation"),
    ):
        apply_authorized_lead_workflow_transition(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.REVIEW,
            next_status=LeadWorkflowStatus.READY,
            reason="attempt stale transition",
            caller_confirmation=True,
            operator_id="operator:tyler",
        )

    assert executor.calls == []


def test_exact_replay_returns_transition_without_repeating_database_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    executor = _Executor()
    monkeypatch.setattr(
        transition_service,
        "transition_persisted_lead_workflow",
        executor,
    )

    with managed_session(factory) as session:
        first = apply_authorized_lead_workflow_transition(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="review new evidence",
            caller_confirmation=True,
            operator_id="operator:tyler",
        )
        assert first.report.current_status == "review"
        replay = apply_authorized_lead_workflow_transition(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="review new evidence",
            caller_confirmation=True,
            operator_id="operator:tyler",
        )

    assert replay.report == first.report
    assert len(executor.calls) == 1


def test_authorized_transition_preserves_existing_mutation_service() -> None:
    factory = _factory()

    with managed_session(factory) as session:
        result = apply_authorized_lead_workflow_transition(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="review new evidence",
            caller_confirmation=True,
            operator_id="operator:tyler",
        )

    assert result.report.previous_status == "monitor"
    assert result.report.current_status == "review"
    assert result.authorization.decision.action == "transition-lead-workflow"


def test_transition_facade_rejects_effect_and_consumption_injection() -> None:
    parameters = inspect.signature(apply_authorized_lead_workflow_transition).parameters
    assert "executor" not in parameters
    assert "ledger" not in parameters
    assert "now" not in parameters
    assert "consumption_store" not in parameters


def test_concurrent_database_writers_apply_exact_transition_at_most_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "workflow.sqlite3"
    factory = _factory(f"sqlite+pysqlite:///{database_path}")
    rendezvous = Barrier(2)
    real_load = transition_service.load_persisted_lead_workflow

    def synchronized_load(session, workflow_id: str):
        workflow = real_load(session, workflow_id)
        rendezvous.wait(timeout=10)
        return workflow

    monkeypatch.setattr(
        transition_service,
        "load_persisted_lead_workflow",
        synchronized_load,
    )

    def attempt():
        try:
            with managed_session(factory) as session:
                result = apply_authorized_lead_workflow_transition(
                    session,
                    workflow_id="lead-workflow:test",
                    expected_current_status=LeadWorkflowStatus.MONITOR,
                    next_status=LeadWorkflowStatus.REVIEW,
                    reason="review concurrent evidence",
                    caller_confirmation=True,
                    operator_id="operator:tyler",
                )
            return result.report
        except EffectOutcomeUnavailableError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = [future.result(timeout=15) for future in [
            executor.submit(attempt),
            executor.submit(attempt),
        ]]

    with managed_session(factory) as session:
        persisted = real_load(session, "lead-workflow:test")
    assert persisted.status is LeadWorkflowStatus.REVIEW
    assert len(persisted.events) == 2
    assert sum(isinstance(item, LeadWorkflowTransitionReport) for item in outcomes) >= 1
