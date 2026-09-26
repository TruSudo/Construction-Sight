"""ConstructionSight-owned reservation and exact-result replay boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, TypeVar

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.effect_consumption_models import (
    EffectOperation,
    EffectReplayPolicy,
)
from constructionsight.local_operator_authorization import LocalAuthorizationResult
from constructionsight.storage.effect_consumption_store import (
    EffectConsumptionError,
    EffectConsumptionStore,
)

T = TypeVar("T")

_APPLICATION_ROOT = Path(__file__).resolve().parents[2]
_CONSUMPTION_DATABASE_PATH = (
    _APPLICATION_ROOT / "data" / "constructionsight-effect-consumption.sqlite3"
)
_MAX_RESULT_BYTES = 25_000_000


def trusted_utc_now() -> datetime:
    """Acquire authoritative production time without a caller-visible clock seam."""

    return datetime.now(UTC)


def _owned_store() -> EffectConsumptionStore:
    """Return the one canonical application-owned protected-effect ledger."""

    path = _CONSUMPTION_DATABASE_PATH
    if not path.is_absolute():
        raise EffectConsumptionError("consumption database path must be absolute")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink() or parent.resolve() != parent:
        raise EffectConsumptionError(
            "consumption database parent must be a canonical non-symlink directory"
        )
    if path.exists() and path.is_symlink():
        raise EffectConsumptionError("consumption database must not be a symbolic link")
    return EffectConsumptionStore(path)


def _canonical_result(payload: Mapping[str, Any]) -> str:
    try:
        rendered = json.dumps(
            dict(payload),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise EffectConsumptionError(
            "protected effect result is not canonical plain JSON"
        ) from exc
    if len(rendered.encode("utf-8")) > _MAX_RESULT_BYTES:
        raise EffectConsumptionError("protected effect result exceeds the retention ceiling")
    return rendered


def _authority_digest(authorization: LocalAuthorizationResult) -> str:
    decision = authorization.decision
    return authorization_digest(
        "logical-authorization",
        {
            "actor_id": decision.actor_id,
            "action": decision.action,
            "resource_type": decision.resource_type,
            "resource_id": decision.resource_id,
            "exact_scope": decision.exact_scope,
            "current_state_identity": decision.current_state_identity,
            "expected_identity": decision.expected_identity,
            "granted_authority": decision.granted_authority,
            "denied_authority": decision.denied_authority,
            "reason": decision.reason,
            "reuse_policy": decision.reuse_policy.value,
            "max_uses": decision.max_uses,
            "revocation_identity": decision.revocation_identity,
            "audit_identity": decision.audit_identity,
            "failure_posture": decision.failure_posture,
            "caller_confirmation": decision.caller_confirmation,
            "limitations": decision.limitations,
        },
    )


def _build_operation(
    authorization: LocalAuthorizationResult,
    *,
    allowance_identity: str,
    content_identity: str,
    implementation_id: str,
    replay_policy: EffectReplayPolicy,
    trusted_at: datetime,
) -> EffectOperation:
    decision = authorization.decision
    preflight = authorization.preflight
    for label, value in {
        "allowance_identity": allowance_identity,
        "content_identity": content_identity,
        "implementation_id": implementation_id,
    }.items():
        if not value.strip() or value != value.strip():
            raise EffectConsumptionError(f"{label} must be nonblank and trimmed")
    if trusted_at < decision.not_before or trusted_at >= decision.expires_at:
        raise EffectConsumptionError(
            "trusted reservation time is outside the authorization validity window"
        )
    if trusted_at >= preflight.valid_until:
        raise EffectConsumptionError("authorization preflight expired before reservation")
    if preflight.decision_id != decision.decision_id:
        raise EffectConsumptionError("authorization and preflight identities are not bound")
    authority_identity = _authority_digest(authorization)
    exact_scope_digest = authorization_digest(
        "effect-exact-scope",
        {"values": decision.exact_scope},
    )
    reservation_key = authorization_digest(
        "effect-reservation",
        {
            "actor_id": decision.actor_id,
            "action": decision.action,
            "resource_type": decision.resource_type,
            "resource_id": decision.resource_id,
            "allowance_identity": allowance_identity,
        },
    )
    operation_payload = {
        "reservation_key": reservation_key,
        "authority_digest": authority_identity,
        "actor_id": decision.actor_id,
        "action": decision.action,
        "resource_type": decision.resource_type,
        "resource_id": decision.resource_id,
        "exact_scope_digest": exact_scope_digest,
        "current_state_identity": decision.current_state_identity,
        "expected_identity": decision.expected_identity,
        "revocation_identity": decision.revocation_identity,
        "allowance_identity": allowance_identity,
        "content_identity": content_identity,
        "implementation_id": implementation_id,
        "replay_policy": replay_policy.value,
    }
    return EffectOperation(
        reservation_key=reservation_key,
        operation_digest=authorization_digest("effect-operation", operation_payload),
        decision_id=decision.decision_id,
        authority_digest=authority_identity,
        actor_id=decision.actor_id,
        action=decision.action,
        resource_type=decision.resource_type,
        resource_id=decision.resource_id,
        exact_scope_digest=exact_scope_digest,
        current_state_identity=decision.current_state_identity,
        allowance_identity=allowance_identity,
        content_identity=content_identity,
        implementation_id=implementation_id,
        replay_policy=replay_policy,
    )


def _execute_owned_effect(
    authorization: LocalAuthorizationResult,
    *,
    allowance_identity: str,
    content_identity: str,
    implementation_id: str,
    replay_policy: EffectReplayPolicy,
    effect: Callable[[datetime], T],
    encode_result: Callable[[T], Mapping[str, Any]],
    decode_result: Callable[[Mapping[str, Any]], T],
    required_utc_date: date | None = None,
) -> T:
    """Reserve, invoke one statically owned effect, and retain its terminal result."""

    reserved_at = trusted_utc_now()
    if required_utc_date is not None and reserved_at.date() != required_utc_date:
        raise EffectConsumptionError(
            "trusted UTC date disagrees with the requested allowance date"
        )
    operation = _build_operation(
        authorization,
        allowance_identity=allowance_identity,
        content_identity=content_identity,
        implementation_id=implementation_id,
        replay_policy=replay_policy,
        trusted_at=reserved_at,
    )
    store = _owned_store()
    reservation = store.reserve(operation, reserved_at=reserved_at)
    if reservation.exact_replay:
        result_json = reservation.record.result_json
        result_digest = reservation.record.result_digest
        if result_json is None or result_digest is None:
            raise EffectConsumptionError("exact replay has no committed result")
        if authorization_digest("effect-result", json.loads(result_json)) != result_digest:
            raise EffectConsumptionError("retained exact replay result failed integrity")
        payload = json.loads(result_json)
        if not isinstance(payload, dict):
            raise EffectConsumptionError("retained exact replay result is not an object")
        return decode_result(payload)

    effect_started = False
    try:
        started_at = trusted_utc_now()
        if required_utc_date is not None and started_at.date() != required_utc_date:
            raise EffectConsumptionError(
                "trusted UTC date changed before protected effect start"
            )
        store.mark_effect_started(operation, started_at=started_at)
        effect_started = True
        result = effect(started_at)
        result_payload = encode_result(result)
        result_json = _canonical_result(result_payload)
        normalized_payload = json.loads(result_json)
        if not isinstance(normalized_payload, dict):
            raise EffectConsumptionError("protected effect result must be an object")
        store.commit_success(
            operation,
            completed_at=trusted_utc_now(),
            result_json=result_json,
            result_digest=authorization_digest("effect-result", normalized_payload),
        )
        return result
    except Exception as exc:
        store.commit_failure(
            operation,
            completed_at=trusted_utc_now(),
            effect_started=effect_started,
            failure_type=f"{type(exc).__module__}.{type(exc).__qualname__}",
            failure_digest=authorization_digest(
                "effect-failure",
                {
                    "type": f"{type(exc).__module__}.{type(exc).__qualname__}",
                    "message": str(exc),
                    "effect_started": effect_started,
                },
            ),
        )
        raise
