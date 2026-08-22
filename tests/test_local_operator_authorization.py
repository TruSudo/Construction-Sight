from __future__ import annotations

import inspect
import io
import json
from datetime import UTC, datetime

import pytest

import constructionsight.local_operator_authorization as authorization_module
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def _authorize(
    *,
    confirmation: bool = True,
    operator_id: str = "operator:Cafe\u0301",
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


def test_repeated_validation_does_not_consume_the_protected_effect() -> None:
    first = _authorize()
    second = _authorize()

    assert first.preflight.use_available is True
    assert second.preflight.use_available is True


def test_production_authorizer_exposes_no_clock_or_consumption_backend() -> None:
    parameters = inspect.signature(authorize_local_operator_operation).parameters

    assert "now" not in parameters
    assert "ledger" not in parameters
    assert "consumption_store" not in parameters


def test_naive_owned_authorization_clock_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        authorization_module,
        "_trusted_authorization_time",
        lambda: datetime(2026, 7, 15, 12, 0),
    )
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
            audit_stream=io.StringIO(),
        )
