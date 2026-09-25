from __future__ import annotations

import inspect
from datetime import UTC, datetime

import pytest

import constructionsight.operator_services.result_authority_apply_service as result_apply_service
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)
from constructionsight.operator_services.result_authority_apply_service import (
    apply_authorized_authoritative_result,
)
from constructionsight.result_authority_models import (
    ResultAuthorityApplyReport,
    ResultAuthorityEvent,
    ResultAuthorityHead,
)
from constructionsight.result_authority_service import ResultAuthorityError
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.result_ledger_service import build_result_ledger_record
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
        status=LeadWorkflowStatus.REVIEW,
        lead_score=82,
        events=[
            LeadWorkflowEvent(
                event_id="lead-workflow-event:initial",
                current_status=LeadWorkflowStatus.REVIEW,
                reason="review completed",
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
        expected_current_ledger_id,
        status,
        authority_reason,
        decided_date=None,
        gross_value=None,
        share_rate=None,
        outcome_reasons=None,
    ) -> ResultAuthorityApplyReport:
        del session, expected_current_ledger_id, decided_date, share_rate
        self.calls.append((workflow_id, status.value, authority_reason))
        ledger = build_result_ledger_record(
            workflow=_workflow(),
            status=status,
            gross_value=gross_value,
            reasons=outcome_reasons,
        )
        return ResultAuthorityApplyReport(
            previous_ledger_id=None,
            current=ledger,
            head=ResultAuthorityHead(
                workflow_id=workflow_id,
                current_ledger_id=ledger.ledger_id,
                current_revision=ledger.revision,
                updated_at=_NOW,
            ),
            event=ResultAuthorityEvent(
                event_id="result-authority-event:test",
                workflow_id=workflow_id,
                previous_ledger_id=None,
                current_ledger_id=ledger.ledger_id,
                current_content_digest=ledger.content_digest,
                revision=ledger.revision,
                reason=authority_reason,
                created_at=_NOW,
            ),
        )


def _apply(
    monkeypatch: pytest.MonkeyPatch,
    session,
    executor=None,
    *,
    confirmation: bool = True,
    expected_current_ledger_id: str | None = None,
):
    if executor is not None:
        monkeypatch.setattr(result_apply_service, "apply_authoritative_result", executor)
    return apply_authorized_authoritative_result(
        session,
        workflow_id="lead-workflow:test",
        expected_current_ledger_id=expected_current_ledger_id,
        status=ResultLedgerStatus.WON,
        authorization_reason="Record the reviewed contract result.",
        caller_confirmation=confirmation,
        gross_value=2500.0,
        outcome_reasons=["operator confirmed contract result"],
        operator_id="operator:tyler",
    )


def test_result_authority_requires_scope_bound_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    executor = _Executor()

    with (
        managed_session(factory) as session,
        pytest.raises(AuthorizationDeniedError, match="in addition"),
    ):
        _apply(monkeypatch, session, executor, confirmation=False)

    assert executor.calls == []


def test_result_authority_rejects_stale_expected_ledger_before_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    executor = _Executor()

    with (
        managed_session(factory) as session,
        pytest.raises(ResultAuthorityError, match="operator expectation"),
    ):
        _apply(
            monkeypatch,
            session,
            executor,
            expected_current_ledger_id="result-ledger:missing",
        )

    assert executor.calls == []


def test_exact_replay_returns_result_without_repeating_database_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    executor = _Executor()
    with managed_session(factory) as session:
        first = _apply(monkeypatch, session, executor)
        assert first.report.current.status is ResultLedgerStatus.WON
        replay = _apply(monkeypatch, session, executor)

    assert replay.report == first.report
    assert len(executor.calls) == 1


def test_authorized_result_preserves_serialized_mutation_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()

    with managed_session(factory) as session:
        result = _apply(monkeypatch, session)

    assert result.report.previous_ledger_id is None
    assert result.report.current.status is ResultLedgerStatus.WON
    assert result.authorization.decision.action == "apply-authoritative-result"


def test_result_facade_rejects_effect_and_consumption_injection() -> None:
    parameters = inspect.signature(apply_authorized_authoritative_result).parameters
    assert "executor" not in parameters
    assert "ledger" not in parameters
    assert "now" not in parameters
    assert "consumption_store" not in parameters
