"""Scope-bound application facade for atomic CEQAnet write-plan persistence."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from constructionsight.authorization_decision import AuthorizationUseLedger
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_persistence_execute import (
    CeqanetPersistenceExecutionResult,
    execute_ceqanet_write_plan,
    validate_ceqanet_write_plan,
)
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.storage.database import create_database_engine


class PersistenceExecutor(Protocol):
    """Atomic persistence interface used by the facade and deterministic tests."""

    def __call__(
        self,
        write_plan_payload: dict[str, Any],
        database_url: str,
    ) -> CeqanetPersistenceExecutionResult:
        """Persist one completely validated write plan."""


@dataclass(frozen=True)
class AuthorizedPersistenceResult:
    """Atomic persistence result and its claimed authorization."""

    execution: CeqanetPersistenceExecutionResult
    authorization: LocalAuthorizationResult


def _execute_persistence(
    write_plan_payload: dict[str, Any],
    database_url: str,
) -> CeqanetPersistenceExecutionResult:
    engine = create_database_engine(database_url)
    return execute_ceqanet_write_plan(write_plan_payload, engine=engine)


def execute_authorized_ceqanet_write_plan(
    *,
    write_plan_payload: dict[str, Any],
    database_url: str,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    executor: PersistenceExecutor | None = None,
) -> AuthorizedPersistenceResult:
    """Authorize and atomically apply one exact reviewed write plan."""

    operation_count, operation_ids = validate_ceqanet_write_plan(write_plan_payload)
    if not database_url.strip():
        raise ValueError("database_url must be nonblank")
    plan_digest = authorization_digest(
        "ceqanet-write-plan",
        write_plan_payload,
    )
    destination_identity = authorization_digest(
        "ceqanet-persistence-destination",
        {"database_url": database_url},
    )
    current_state_identity = authorization_digest(
        "ceqanet-persistence-current-state",
        {
            "plan_digest": plan_digest,
            "destination_identity": destination_identity,
            "operation_ids": operation_ids,
        },
    )
    operation_ids_digest = authorization_digest(
        "ceqanet-operation-ids",
        {"ids": operation_ids},
    )
    exact_scope = tuple(
        sorted(
            {
                f"destination:{destination_identity}",
                f"operation-count:{operation_count}",
                f"operation-id-digest:{operation_ids_digest}",
                f"plan-digest:{plan_digest}",
                "transaction:all-or-nothing",
                "write-mode:upsert-preview-only",
            },
            key=str.casefold,
        )
    )
    authorization = authorize_local_operator_operation(
        action="execute-ceqanet-write-plan",
        resource_type="ceqanet-write-plan",
        resource_id=plan_digest,
        exact_scope=exact_scope,
        current_state_identity=current_state_identity,
        expected_identity=current_state_identity,
        granted_authority=(
            "atomically apply one exact reviewed CEQAnet write plan",
        ),
        denied_authority=tuple(
            sorted(
                {
                    "automatic recurrence",
                    "credential acquisition",
                    "destructive overwrite",
                    "generic record editing",
                    "network execution",
                    "partial commit",
                    "plan mutation",
                    "source promotion",
                    "unreviewed operation",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=tuple(
            sorted(
                {
                    "database credentials are not granted by this decision",
                    "local operator identity is not authentication",
                    "persistence does not authorize network execution or source promotion",
                    "single local-process transaction only",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=current_state_identity,
        now=now,
        ledger=ledger,
    )
    active_executor: PersistenceExecutor = executor or _execute_persistence
    execution = active_executor(write_plan_payload, database_url)
    if execution.failed_count or execution.skipped_count:
        raise RuntimeError(
            "atomic persistence executor returned a partial result contract violation"
        )
    if execution.applied_count != operation_count:
        raise RuntimeError(
            "atomic persistence executor applied count disagrees with reviewed plan"
        )
    return AuthorizedPersistenceResult(
        execution=execution,
        authorization=authorization,
    )
