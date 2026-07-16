"""Canonical local-process authorization for high-impact operator services."""

from __future__ import annotations

import getpass
import json
import os
import sys
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TextIO

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
    authorize_and_claim,
    build_authorization_decision,
)
from constructionsight.authorization_decision_models import (
    AuthorizationDecision,
    AuthorizationPreflight,
    AuthorizationReusePolicy,
    authorization_digest,
)

_AUTHORIZATION_TTL = timedelta(minutes=5)


@dataclass(frozen=True)
class LocalAuthorizationResult:
    """Completed decision and claimed preflight for one local operation."""

    decision: AuthorizationDecision
    preflight: AuthorizationPreflight

    def to_dict(self) -> dict[str, object]:
        """Return stable audit metadata without reproducing sensitive scope values."""

        return {
            "decision_id": self.decision.decision_id,
            "preflight_id": self.preflight.preflight_id,
            "actor_id": self.decision.actor_id,
            "action": self.decision.action,
            "resource_type": self.decision.resource_type,
            "resource_id": self.decision.resource_id,
            "audit_identity": self.decision.audit_identity,
            "claim_audit_identity": self.preflight.audit_identity,
            "valid_until": self.preflight.valid_until.isoformat(),
            "granted_authority": list(self.decision.granted_authority),
            "denied_authority": list(self.decision.denied_authority),
            "limitations": list(self.decision.limitations),
        }


def _normalized_text(value: str, *, field: str) -> str:
    normalized = unicodedata.normalize("NFC", value).strip()
    if not normalized:
        raise ValueError(f"{field} must be nonblank")
    return normalized


def _canonical_values(values: Iterable[str], *, field: str) -> tuple[str, ...]:
    normalized = tuple(_normalized_text(value, field=field) for value in values)
    if not normalized:
        raise ValueError(f"{field} must contain at least one value")
    return tuple(sorted(set(normalized), key=str.casefold))


def resolve_local_operator_id(explicit_operator_id: str | None = None) -> str:
    """Resolve the local audit identity; this is never treated as authentication."""

    candidate = (
        explicit_operator_id
        or os.environ.get("CONSTRUCTIONSIGHT_OPERATOR_ID")
        or getpass.getuser()
    )
    return _normalized_text(candidate, field="operator_id")


def _emit_audit_event(
    result: LocalAuthorizationResult,
    *,
    exact_scope: tuple[str, ...],
    reason: str,
    stream: TextIO,
) -> None:
    event = {
        "schema_version": "constructionsight.local-authorization-audit/v1",
        "decision_id": result.decision.decision_id,
        "preflight_id": result.preflight.preflight_id,
        "actor_id": result.decision.actor_id,
        "action": result.decision.action,
        "resource_type": result.decision.resource_type,
        "resource_id": result.decision.resource_id,
        "scope_digest": authorization_digest(
            "local-authorization-scope",
            {"values": exact_scope},
        ),
        "reason_digest": authorization_digest(
            "local-authorization-reason",
            {"reason": reason},
        ),
        "audit_identity": result.decision.audit_identity,
        "claim_audit_identity": result.preflight.audit_identity,
        "checked_at": result.preflight.checked_at.isoformat(),
        "valid_until": result.preflight.valid_until.isoformat(),
        "granted_authority": list(result.decision.granted_authority),
        "denied_authority": list(result.decision.denied_authority),
        "limitations": list(result.decision.limitations),
        "failure_posture": result.decision.failure_posture,
    }
    stream.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
    stream.flush()


def authorize_local_operator_operation(
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    exact_scope: Iterable[str],
    current_state_identity: str,
    expected_identity: str,
    granted_authority: Iterable[str],
    denied_authority: Iterable[str],
    reason: str,
    caller_confirmation: bool,
    limitations: Iterable[str],
    operator_id: str | None = None,
    current_revocation_identity: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    audit_stream: TextIO | None = None,
) -> LocalAuthorizationResult:
    """Issue, verify, claim, and audit one exact local-process authorization."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "caller confirmation is required in addition to scope-bound authority"
        )

    actor = resolve_local_operator_id(operator_id)
    normalized_action = _normalized_text(action, field="action")
    normalized_resource_type = _normalized_text(
        resource_type,
        field="resource_type",
    )
    normalized_resource_id = _normalized_text(resource_id, field="resource_id")
    normalized_state = _normalized_text(
        current_state_identity,
        field="current_state_identity",
    )
    normalized_expected = _normalized_text(
        expected_identity,
        field="expected_identity",
    )
    normalized_reason = _normalized_text(reason, field="reason")
    scope = _canonical_values(exact_scope, field="exact_scope")
    grants = _canonical_values(granted_authority, field="granted_authority")
    denials = _canonical_values(denied_authority, field="denied_authority")
    normalized_limitations = _canonical_values(limitations, field="limitations")

    checked_at = (now or (lambda: datetime.now(UTC)))()
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("authorization clock must return a timezone-aware datetime")

    environment_revocation = os.environ.get("CONSTRUCTIONSIGHT_REVOCATION_ID")
    revocation_identity = _normalized_text(
        current_revocation_identity or environment_revocation or normalized_state,
        field="current_revocation_identity",
    )
    audit_identity = authorization_digest(
        "local-operator-audit",
        {
            "actor_id": actor,
            "action": normalized_action,
            "resource_type": normalized_resource_type,
            "resource_id": normalized_resource_id,
            "scope": scope,
            "current_state_identity": normalized_state,
            "expected_identity": normalized_expected,
            "revocation_identity": revocation_identity,
            "reason": normalized_reason,
        },
    )
    decision = build_authorization_decision(
        actor_id=actor,
        action=normalized_action,
        resource_type=normalized_resource_type,
        resource_id=normalized_resource_id,
        exact_scope=scope,
        current_state_identity=normalized_state,
        expected_identity=normalized_expected,
        granted_authority=grants,
        denied_authority=denials,
        reason=normalized_reason,
        issued_at=checked_at,
        not_before=checked_at,
        expires_at=checked_at + _AUTHORIZATION_TTL,
        reuse_policy=AuthorizationReusePolicy.SINGLE_USE,
        revocation_identity=revocation_identity,
        audit_identity=audit_identity,
        caller_confirmation=True,
        limitations=normalized_limitations,
    )
    replay_identity = authorization_digest(
        "local-operator-attempt",
        {
            "decision_id": decision.decision_id,
            "resource_id": normalized_resource_id,
            "scope": scope,
        },
    )
    preflight = authorize_and_claim(
        decision,
        actor_id=actor,
        action=normalized_action,
        resource_type=normalized_resource_type,
        resource_id=normalized_resource_id,
        exact_scope=scope,
        current_state_identity=normalized_state,
        current_revocation_identity=revocation_identity,
        replay_identity=replay_identity,
        checked_at=checked_at,
        ledger=ledger if ledger is not None else AuthorizationUseLedger(),
    )
    result = LocalAuthorizationResult(decision=decision, preflight=preflight)
    _emit_audit_event(
        result,
        exact_scope=scope,
        reason=normalized_reason,
        stream=audit_stream or sys.stderr,
    )
    return result
