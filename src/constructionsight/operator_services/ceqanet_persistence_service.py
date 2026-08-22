"""Scope-bound application facade for atomic CEQAnet write-plan persistence."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
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


@dataclass(frozen=True)
class AuthorizedPersistenceResult:
    """Atomic persistence result and its claimed authorization."""

    execution: CeqanetPersistenceExecutionResult
    authorization: LocalAuthorizationResult


@dataclass(frozen=True)
class _CanonicalWritePlanSnapshot:
    """Immutable content boundary between caller input and persistence execution."""

    canonical_payload: bytes
    plan_digest: str
    operation_count: int
    operation_ids: tuple[str, ...]


def _require_plain_json(value: object, *, path: str) -> None:
    """Reject values whose JSON conversion could silently change reviewed content."""

    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"write-plan value at {path} must be finite")
        return
    if type(value) is list:
        for index, item in enumerate(cast(list[object], value)):
            _require_plain_json(item, path=f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, item in cast(dict[object, object], value).items():
            if type(key) is not str:
                raise ValueError(f"write-plan object key at {path} must be a string")
            _require_plain_json(item, path=f"{path}.{key}")
        return
    raise ValueError(f"write-plan value at {path} must use plain JSON types")


def _canonical_write_plan_payload(write_plan_payload: dict[str, Any]) -> bytes:
    """Render a deterministic immutable snapshot without retaining caller objects."""

    _require_plain_json(write_plan_payload, path="$")
    try:
        return json.dumps(
            write_plan_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ValueError("write plan cannot be represented as canonical JSON") from exc


def _materialize_write_plan_snapshot(canonical_payload: bytes) -> dict[str, Any]:
    """Create a fresh execution payload solely from immutable canonical bytes."""

    try:
        candidate = json.loads(canonical_payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise AuthorizationDeniedError("canonical write-plan snapshot is malformed") from exc
    if type(candidate) is not dict:
        raise AuthorizationDeniedError("canonical write-plan snapshot must be an object")
    return cast(dict[str, Any], candidate)


def _write_plan_identity(write_plan_payload: dict[str, Any]) -> str:
    return authorization_digest("ceqanet-write-plan", write_plan_payload)


def _build_write_plan_snapshot(
    write_plan_payload: dict[str, Any],
) -> _CanonicalWritePlanSnapshot:
    canonical_payload = _canonical_write_plan_payload(write_plan_payload)
    detached_payload = _materialize_write_plan_snapshot(canonical_payload)
    operation_count, operation_ids = validate_ceqanet_write_plan(detached_payload)
    return _CanonicalWritePlanSnapshot(
        canonical_payload=canonical_payload,
        plan_digest=_write_plan_identity(detached_payload),
        operation_count=operation_count,
        operation_ids=operation_ids,
    )


def _verified_execution_payload(
    snapshot: _CanonicalWritePlanSnapshot,
) -> dict[str, Any]:
    """Recheck exact snapshot identity immediately before the persistence effect."""

    execution_payload = _materialize_write_plan_snapshot(snapshot.canonical_payload)
    operation_count, operation_ids = validate_ceqanet_write_plan(execution_payload)
    current_plan_digest = _write_plan_identity(execution_payload)
    if current_plan_digest != snapshot.plan_digest:
        raise AuthorizationDeniedError(
            "detached write-plan snapshot identity changed after authorization"
        )
    if _canonical_write_plan_payload(execution_payload) != snapshot.canonical_payload:
        raise AuthorizationDeniedError(
            "detached write-plan snapshot canonical content changed after authorization"
        )
    if (
        operation_count != snapshot.operation_count
        or operation_ids != snapshot.operation_ids
    ):
        raise AuthorizationDeniedError(
            "detached write-plan snapshot operations changed after authorization"
        )
    return execution_payload


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
) -> AuthorizedPersistenceResult:
    """Authorize and atomically apply one exact reviewed write plan."""

    snapshot = _build_write_plan_snapshot(write_plan_payload)
    if not database_url.strip():
        raise ValueError("database_url must be nonblank")
    operation_count = snapshot.operation_count
    operation_ids = snapshot.operation_ids
    plan_digest = snapshot.plan_digest
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
    execution_payload = _verified_execution_payload(snapshot)
    execution = _execute_persistence(execution_payload, database_url)
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
