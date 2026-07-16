from __future__ import annotations

import io
import json
from datetime import UTC, datetime

import pytest

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def _authorize(
    *,
    confirmation: bool = True,
    operator_id: str = "operator:Cafe\u0301",
    ledger: AuthorizationUseLedger | None = None,
    audit_stream: io.StringIO | None = None,
):
    return authorize_local_operator_operation(
        action="execute-test-operation",
        resource_type="test-resource",
        resource_id="resource:1",
        exact_scope=("url:https://example.test/?token=secret", "method:GET"),
        current_state_identity="state:1",
        expected_identity="state:1",
        granted_authority=("execute one exact test operation",),
        denied_authority=("credential use", "repeat execution"),
        reason="Exercise token=secret without exposing it in the audit event.",
        caller_confirmation=confirmation,
        limitations=("local identity is not authentication",),
        operator_id=operator_id,
        now=lambda: _NOW,
        ledger=ledger,
        audit_stream=audit_stream,
    )


def test_local_authorization_normalizes_identity_and_emits_redacted_audit() -> None:
    stream = io.StringIO()

    result = _authorize(audit_stream=stream)

    assert result.decision.actor_id == "operator:Caf\u00e9"
    payload = json.loads(stream.getvalue())
    assert payload["decision_id"] == result.decision.decision_id
    assert payload["preflight_id"] == result.preflight.preflight_id
    assert "secret" not in stream.getvalue()
    assert "scope_digest" in payload
    assert "reason_digest" in payload


def test_boolean_confirmation_is_not_authority() -> None:
    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _authorize(confirmation=False)


def test_shared_ledger_rejects_repeated_local_authorization() -> None:
    ledger = AuthorizationUseLedger()

    first = _authorize(ledger=ledger)
    assert first.preflight.use_available is True
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _authorize(ledger=ledger)


def test_naive_authorization_clock_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        authorize_local_operator_operation(
            action="execute-test-operation",
            resource_type="test-resource",
            resource_id="resource:1",
            exact_scope=("method:GET",),
            current_state_identity="state:1",
            expected_identity="state:1",
            granted_authority=("execute one exact test operation",),
            denied_authority=("repeat execution",),
            reason="Test a naive clock.",
            caller_confirmation=True,
            limitations=("local identity is not authentication",),
            operator_id="operator:test",
            now=lambda: datetime(2026, 7, 15, 12, 0),
            audit_stream=io.StringIO(),
        )
