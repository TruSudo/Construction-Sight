"""Fail-closed preflight and atomic use-claim for semantic authorization."""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

from constructionsight.authorization_decision_models import (
    AuthorizationDecision,
    AuthorizationPreflight,
    AuthorizationReusePolicy,
    authorization_digest,
)


class AuthorizationDeniedError(RuntimeError):
    """Raised when exact authority is absent, stale, expired, revoked, or consumed."""


class AuthorizationUseLedger:
    """Thread-safe local-process claim ledger for current CLI execution.

    This ledger prevents concurrent reuse inside one process. It is not a hosted,
    multi-process, or tenant-isolation claim. Persistent cross-process consumption is
    a mandatory entry condition before a scheduler or hosted GUI may use this model.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._claims: dict[str, str] = {}

    def claim(
        self,
        decision: AuthorizationDecision,
        *,
        replay_identity: str,
    ) -> LiteralClaimResult:
        """Atomically claim one decision or recognize its exact idempotent replay."""

        if not replay_identity.strip() or replay_identity != replay_identity.strip():
            raise AuthorizationDeniedError("replay identity must be nonblank and trimmed")
        with self._lock:
            existing = self._claims.get(decision.decision_id)
            if existing is None:
                self._claims[decision.decision_id] = replay_identity
                return "claimed"
            if (
                decision.reuse_policy is AuthorizationReusePolicy.EXACT_REPLAY
                and existing == replay_identity
            ):
                return "exact_replay"
            if decision.reuse_policy is AuthorizationReusePolicy.EXACT_REPLAY:
                raise AuthorizationDeniedError(
                    "authorization was already consumed by a conflicting replay identity"
                )
            raise AuthorizationDeniedError("single-use authorization was already consumed")

    def is_claimed(self, decision_id: str) -> bool:
        """Return whether the local process has consumed the decision."""

        with self._lock:
            return decision_id in self._claims


LiteralClaimResult = str


def build_authorization_decision(
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    exact_scope: tuple[str, ...],
    current_state_identity: str,
    expected_identity: str,
    granted_authority: tuple[str, ...],
    denied_authority: tuple[str, ...],
    reason: str,
    issued_at: datetime,
    not_before: datetime,
    expires_at: datetime,
    reuse_policy: AuthorizationReusePolicy,
    revocation_identity: str,
    audit_identity: str,
    caller_confirmation: bool,
    limitations: tuple[str, ...],
) -> AuthorizationDecision:
    """Build one content-bound decision after canonical field validation."""

    payload: dict[str, Any] = {
        "schema_version": "constructionsight.authorization-decision/v1",
        "actor_id": actor_id,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "exact_scope": exact_scope,
        "current_state_identity": current_state_identity,
        "expected_identity": expected_identity,
        "granted_authority": granted_authority,
        "denied_authority": denied_authority,
        "reason": reason,
        "issued_at": issued_at,
        "not_before": not_before,
        "expires_at": expires_at,
        "reuse_policy": reuse_policy,
        "max_uses": 1,
        "revocation_identity": revocation_identity,
        "audit_identity": audit_identity,
        "failure_posture": "fail_closed",
        "caller_confirmation": caller_confirmation,
        "limitations": limitations,
    }
    json_payload = AuthorizationDecision.model_validate(
        {
            **payload,
            "decision_id": "authorization-decision:" + "0" * 64,
        }
    ).model_dump(mode="json", exclude={"decision_id"})
    payload["decision_id"] = authorization_digest(
        "authorization-decision",
        json_payload,
    )
    return AuthorizationDecision.model_validate(payload)


def authorize_and_claim(
    decision: AuthorizationDecision,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    exact_scope: tuple[str, ...],
    current_state_identity: str,
    current_revocation_identity: str,
    replay_identity: str,
    checked_at: datetime,
    ledger: AuthorizationUseLedger,
) -> AuthorizationPreflight:
    """Validate exact authority and atomically claim its local-process use."""

    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise AuthorizationDeniedError("authorization preflight time must be aware")
    if decision.decision_id != authorization_digest(
        "authorization-decision",
        decision.identity_payload(),
    ):
        raise AuthorizationDeniedError("authorization decision integrity failed")
    comparisons = {
        "actor": (actor_id, decision.actor_id),
        "action": (action, decision.action),
        "resource_type": (resource_type, decision.resource_type),
        "resource_id": (resource_id, decision.resource_id),
        "exact_scope": (exact_scope, decision.exact_scope),
        "current_state_identity": (
            current_state_identity,
            decision.expected_identity,
        ),
        "revocation_identity": (
            current_revocation_identity,
            decision.revocation_identity,
        ),
    }
    mismatches = [
        name for name, (actual, expected) in comparisons.items() if actual != expected
    ]
    if mismatches:
        raise AuthorizationDeniedError(
            "authorization exact-scope or current-state mismatch: "
            + ", ".join(sorted(mismatches))
        )
    if checked_at < decision.not_before:
        raise AuthorizationDeniedError("authorization is not yet valid")
    if checked_at >= decision.expires_at:
        raise AuthorizationDeniedError("authorization is expired")
    claim_result = ledger.claim(decision, replay_identity=replay_identity)
    payload: dict[str, Any] = {
        "schema_version": "constructionsight.authorization-preflight/v1",
        "decision_id": decision.decision_id,
        "actor_id": decision.actor_id,
        "action": decision.action,
        "resource_type": decision.resource_type,
        "resource_id": decision.resource_id,
        "checked_at": checked_at,
        "valid_until": decision.expires_at,
        "exact_scope_verified": True,
        "current_state_verified": True,
        "decision_integrity_verified": True,
        "validity_window_verified": True,
        "revocation_verified": True,
        "use_available": True,
        "audit_identity": authorization_digest(
            "authorization-claim",
            {
                "decision_id": decision.decision_id,
                "replay_identity": replay_identity,
                "claim_result": claim_result,
            },
        ),
        "next_action": (
            "return the previously committed exact result without repeating effects"
            if claim_result == "exact_replay"
            else "execute only the exact granted operation and persist its audit event"
        ),
    }
    identity_payload = AuthorizationPreflight.model_validate(
        {
            **payload,
            "preflight_id": "authorization-preflight:" + "0" * 64,
        }
    ).model_dump(mode="json", exclude={"preflight_id"})
    payload["preflight_id"] = authorization_digest(
        "authorization-preflight",
        identity_payload,
    )
    return AuthorizationPreflight.model_validate(payload)
