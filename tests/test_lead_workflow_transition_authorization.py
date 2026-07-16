from __future__ import annotations

from datetime import UTC, datetime

import pytest

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
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
from constructionsight.storage.lead_workflow_store import store_lead_workflow_record

_NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


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


def _factory():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
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


def test_transition_requires_scope_bound_confirmation() -> None:
    factory = _factory()
    executor = _Executor()

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
            now=lambda: _NOW,
            executor=executor,
        )

    assert executor.calls == []


def test_transition_rejects_stale_state_before_mutation() -> None:
    factory = _factory()
    executor = _Executor()

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
            now=lambda: _NOW,
            executor=executor,
        )

    assert executor.calls == []


def test_shared_ledger_rejects_repeated_exact_transition() -> None:
    factory = _factory()
    executor = _Executor()
    ledger = AuthorizationUseLedger()

    with managed_session(factory) as session:
        first = apply_authorized_lead_workflow_transition(
            session,
            workflow_id="lead-workflow:test",
            expected_current_status=LeadWorkflowStatus.MONITOR,
            next_status=LeadWorkflowStatus.REVIEW,
            reason="review new evidence",
            caller_confirmation=True,
            operator_id="operator:tyler",
            now=lambda: _NOW,
            ledger=ledger,
            executor=executor,
        )
        assert first.report.current_status == "review"
        with pytest.raises(AuthorizationDeniedError, match="already consumed"):
            apply_authorized_lead_workflow_transition(
                session,
                workflow_id="lead-workflow:test",
                expected_current_status=LeadWorkflowStatus.MONITOR,
                next_status=LeadWorkflowStatus.REVIEW,
                reason="review new evidence",
                caller_confirmation=True,
                operator_id="operator:tyler",
                now=lambda: _NOW,
                ledger=ledger,
                executor=executor,
            )

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
            now=lambda: _NOW,
        )

    assert result.report.previous_status == "monitor"
    assert result.report.current_status == "review"
    assert result.authorization.decision.action == "transition-lead-workflow"
