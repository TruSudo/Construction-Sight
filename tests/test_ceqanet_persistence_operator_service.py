from __future__ import annotations

from datetime import UTC, datetime

import pytest

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_persistence_execute import (
    CeqanetPersistenceExecutionResult,
)
from constructionsight.operator_services import ceqanet_persistence_service
from constructionsight.operator_services.ceqanet_persistence_service import (
    execute_authorized_ceqanet_write_plan,
)

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def _plan() -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_write_plan.v1",
            "operation_count": 1,
            "skipped_item_count": 0,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "operations": [
            {
                "operation_id": "sites:site:ceqanet:2017101033",
                "action": "upsert_preview",
                "target_collection": "sites",
                "target_key": "site:ceqanet:2017101033",
                "source_index": 0,
                "payload": {
                    "site_key": "site:ceqanet:2017101033",
                    "county": "San Bernardino",
                    "city": "San Bernardino",
                },
            }
        ],
        "skipped_items": [],
    }


class _Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def __call__(self, write_plan_payload, database_url: str):
        operation = write_plan_payload["operations"][0]
        self.calls.append((operation["operation_id"], database_url))
        return CeqanetPersistenceExecutionResult(
            applied_operations=(
                {
                    "operation_id": operation["operation_id"],
                    "source_index": operation["source_index"],
                    "target_collection": operation["target_collection"],
                    "target_key": operation["target_key"],
                    "action": operation["action"],
                },
            )
        )


def _execute(
    executor: _Executor,
    *,
    confirmation: bool = True,
    ledger: AuthorizationUseLedger | None = None,
):
    return execute_authorized_ceqanet_write_plan(
        write_plan_payload=_plan(),
        database_url="sqlite+pysqlite:///:memory:",
        caller_confirmation=confirmation,
        authorization_reason="Apply one reviewed plan atomically.",
        operator_id="operator:tyler",
        now=lambda: _NOW,
        ledger=ledger,
        executor=executor,
    )


def test_persistence_facade_binds_plan_destination_and_atomicity() -> None:
    executor = _Executor()

    result = _execute(executor)

    authorization = result.authorization.to_dict()
    assert authorization["action"] == "execute-ceqanet-write-plan"
    assert "partial commit" in authorization["denied_authority"]
    assert "network execution" in authorization["denied_authority"]
    assert result.execution.applied_count == 1
    assert executor.calls == [
        ("sites:site:ceqanet:2017101033", "sqlite+pysqlite:///:memory:")
    ]


def test_boolean_confirmation_cannot_authorize_persistence() -> None:
    executor = _Executor()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _execute(executor, confirmation=False)

    assert executor.calls == []


def test_shared_ledger_rejects_repeated_persistence() -> None:
    executor = _Executor()
    ledger = AuthorizationUseLedger()

    first = _execute(executor, ledger=ledger)
    assert first.execution.applied_count == 1
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _execute(executor, ledger=ledger)

    assert len(executor.calls) == 1


def test_invalid_plan_is_rejected_before_authorization_or_database_effect() -> None:
    executor = _Executor()
    plan = _plan()
    metadata = plan["metadata"]
    assert isinstance(metadata, dict)
    metadata["operation_count"] = 2

    with pytest.raises(ValueError, match="operation_count"):
        execute_authorized_ceqanet_write_plan(
            write_plan_payload=plan,
            database_url="sqlite+pysqlite:///:memory:",
            caller_confirmation=True,
            authorization_reason="Attempt a drifted plan.",
            operator_id="operator:tyler",
            now=lambda: _NOW,
            executor=executor,
        )

    assert executor.calls == []


def test_persistence_facade_executes_only_a_deeply_detached_snapshot() -> None:
    caller_plan = _plan()
    caller_operations = caller_plan["operations"]
    assert isinstance(caller_operations, list)
    caller_operation = caller_operations[0]
    assert isinstance(caller_operation, dict)
    caller_payload = caller_operation["payload"]
    assert isinstance(caller_payload, dict)
    observed: dict[str, object] = {}

    def executor(write_plan_payload, database_url: str):
        execution_operations = write_plan_payload["operations"]
        execution_operation = execution_operations[0]
        execution_record = execution_operation["payload"]
        observed["plan"] = write_plan_payload
        observed["operations"] = execution_operations
        observed["operation"] = execution_operation
        observed["payload"] = execution_record
        caller_payload["city"] = "Caller mutation at effect boundary"
        assert execution_record["city"] == "San Bernardino"
        return CeqanetPersistenceExecutionResult(
            applied_operations=(
                {
                    "operation_id": execution_operation["operation_id"],
                    "source_index": execution_operation["source_index"],
                    "target_collection": execution_operation["target_collection"],
                    "target_key": execution_operation["target_key"],
                    "action": execution_operation["action"],
                },
            )
        )

    result = execute_authorized_ceqanet_write_plan(
        write_plan_payload=caller_plan,
        database_url="sqlite+pysqlite:///:memory:",
        caller_confirmation=True,
        authorization_reason="Apply a detached reviewed plan.",
        operator_id="operator:tyler",
        now=lambda: _NOW,
        executor=executor,
    )

    assert result.execution.applied_count == 1
    assert observed["plan"] is not caller_plan
    assert observed["operations"] is not caller_operations
    assert observed["operation"] is not caller_operation
    assert observed["payload"] is not caller_payload


def test_authorization_callback_mutation_cannot_change_snapshot_or_effect() -> None:
    caller_plan = _plan()
    reviewed_plan = _plan()
    operations = caller_plan["operations"]
    assert isinstance(operations, list)
    operation = operations[0]
    assert isinstance(operation, dict)
    payload = operation["payload"]
    assert isinstance(payload, dict)
    observed: dict[str, object] = {}

    def mutating_clock() -> datetime:
        operation["operation_id"] = "sites:site:ceqanet:callback-mutation"
        payload["city"] = "Callback mutation"
        return _NOW

    def executor(write_plan_payload, database_url: str):
        del database_url
        execution_operation = write_plan_payload["operations"][0]
        observed["operation_id"] = execution_operation["operation_id"]
        observed["city"] = execution_operation["payload"]["city"]
        return CeqanetPersistenceExecutionResult(
            applied_operations=(
                {
                    "operation_id": execution_operation["operation_id"],
                    "source_index": execution_operation["source_index"],
                    "target_collection": execution_operation["target_collection"],
                    "target_key": execution_operation["target_key"],
                    "action": execution_operation["action"],
                },
            )
        )

    result = execute_authorized_ceqanet_write_plan(
        write_plan_payload=caller_plan,
        database_url="sqlite+pysqlite:///:memory:",
        caller_confirmation=True,
        authorization_reason="Apply the pre-callback reviewed plan.",
        operator_id="operator:tyler",
        now=mutating_clock,
        executor=executor,
    )

    assert observed == {
        "operation_id": "sites:site:ceqanet:2017101033",
        "city": "San Bernardino",
    }
    assert result.authorization.decision.resource_id == authorization_digest(
        "ceqanet-write-plan",
        reviewed_plan,
    )


def test_persistence_facade_rechecks_snapshot_identity_before_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executor = _Executor()
    real_identity = ceqanet_persistence_service._write_plan_identity
    identity_calls = 0

    def drifting_identity(write_plan_payload):
        nonlocal identity_calls
        identity_calls += 1
        identity = real_identity(write_plan_payload)
        if identity_calls == 1:
            return identity
        return f"{identity}-drifted"

    monkeypatch.setattr(
        ceqanet_persistence_service,
        "_write_plan_identity",
        drifting_identity,
    )

    with pytest.raises(AuthorizationDeniedError, match="identity changed"):
        _execute(executor)

    assert identity_calls == 2
    assert executor.calls == []
