"""Fail-closed decision construction and preflight validation."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from constructionsight.authorization_decision_models import (
    AuthorizationDecision,
    AuthorizationPreflight,
    AuthorizationReusePolicy,
    authorization_digest,
)


class AuthorizationDeniedError(RuntimeError):
    """Raised when exact authority is absent, stale, expired, or revoked."""


def _decision_identity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Render fields exactly as the validated decision will hash them."""

    candidate = AuthorizationDecision.model_construct(
        decision_id="authorization-decision:" + "0" * 64,
        **payload,
    )
    return candidate.model_dump(mode="json", exclude={"decision_id"})


def _preflight_identity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Render fields exactly as the validated preflight will hash them."""

    candidate = AuthorizationPreflight.model_construct(
        preflight_id="authorization-preflight:" + "0" * 64,
        **payload,
    )
    return candidate.model_dump(mode="json", exclude={"preflight_id"})


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
    payload["decision_id"] = authorization_digest(
        "authorization-decision",
        _decision_identity_payload(payload),
    )
    return AuthorizationDecision.model_validate(payload)


def validate_authorization_decision(
    decision: AuthorizationDecision,
    *,
    actor_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    exact_scope: tuple[str, ...],
    current_state_identity: str,
    current_revocation_identity: str,
    checked_at: datetime,
) -> AuthorizationPreflight:
    """Validate exact authority without conflating validation with consumption."""

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
            "authorization-validation",
            {
                "decision_id": decision.decision_id,
                "checked_at": checked_at,
                "current_state_identity": current_state_identity,
                "current_revocation_identity": current_revocation_identity,
            },
        ),
        "next_action": (
            "atomically reserve the exact operation in the ConstructionSight-owned "
            "durable consumption store immediately before the protected effect"
        ),
    }
    payload["preflight_id"] = authorization_digest(
        "authorization-preflight",
        _preflight_identity_payload(payload),
    )
    return AuthorizationPreflight.model_validate(payload)
