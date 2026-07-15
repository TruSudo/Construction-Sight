"""Scope-bound application service for one CEQAnet detail-page read."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import urlsplit

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
    authorize_and_claim,
    build_authorization_decision,
)
from constructionsight.authorization_decision_models import (
    AuthorizationReusePolicy,
    authorization_digest,
)
from constructionsight.ceqanet_detail_http import (
    CEQANET_DETAIL_POLICY,
    execute_ceqanet_detail_request,
)
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access

_ACTION = "execute-ceqanet-detail-read"
_RESOURCE_TYPE = "public-ceqanet-detail-page"
_AUTHORIZATION_TTL = timedelta(minutes=5)


class CeqanetDetailExecutor(Protocol):
    """Operation-specific transport interface consumed by the application service."""

    def __call__(
        self,
        url: str,
        *,
        timeout_seconds: float,
        max_body_bytes: int,
    ) -> dict[str, object]:
        """Execute one policy-bound read and return a classified snapshot."""


def _canonical_tuple(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=str.casefold))


def _validated_detail_url(value: str) -> str:
    if value != value.strip():
        raise ValueError("CEQAnet detail URL must be trimmed")
    parsed = urlsplit(value)
    if parsed.scheme != "https":
        raise ValueError("CEQAnet detail execution requires HTTPS")
    if parsed.hostname != "ceqanet.lci.ca.gov" or parsed.username or parsed.password:
        raise ValueError("CEQAnet detail URL must target the exact public CEQAnet host")
    if parsed.port not in {None, 443}:
        raise ValueError("CEQAnet detail URL cannot select a nonstandard port")
    if not parsed.path or parsed.path == "/":
        raise ValueError("CEQAnet detail URL must identify a detail or project path")
    if parsed.fragment:
        raise ValueError("CEQAnet detail URL cannot contain a fragment")
    return value


def _access_state(
    profile: SourceAccessProfile,
    *,
    decision: AccessDecision,
    reason: str,
) -> str:
    return authorization_digest(
        "ceqanet-detail-access-state",
        {
            "public_url": profile.public_url,
            "requires_login": profile.requires_login,
            "has_captcha": profile.has_captcha,
            "robots_disallows_collection": profile.robots_disallows_collection,
            "terms_disallow_collection": profile.terms_disallow_collection,
            "paywalled": profile.paywalled,
            "rate_limit_known": profile.rate_limit_known,
            "rate_limit_notes": profile.rate_limit_notes,
            "decision": decision.value,
            "reason": reason,
        },
    )


def execute_authorized_ceqanet_detail(
    *,
    detail_url: str,
    access_profile: SourceAccessProfile,
    operator_id: str,
    authorization_reason: str,
    caller_confirmation: bool,
    timeout_seconds: float,
    max_body_bytes: int,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    executor: CeqanetDetailExecutor | None = None,
) -> dict[str, object]:
    """Authorize and execute one exact CEQAnet GET without persistence or retry."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "caller confirmation is required in addition to scope-bound authority"
        )
    if not operator_id.strip() or operator_id != operator_id.strip():
        raise ValueError("operator_id must be nonblank and trimmed")
    if not authorization_reason.strip() or authorization_reason != authorization_reason.strip():
        raise ValueError("authorization_reason must be nonblank and trimmed")
    if timeout_seconds <= 0 or timeout_seconds > 120:
        raise ValueError("timeout_seconds must be greater than 0 and at most 120")
    if max_body_bytes < 1 or max_body_bytes > 2_000_000:
        raise ValueError("max_body_bytes must be between 1 and 2000000")

    resolved_url = _validated_detail_url(detail_url)
    access = evaluate_access(access_profile)
    if access.decision is not AccessDecision.ALLOWED:
        raise AuthorizationDeniedError(
            f"lawful access preflight denied execution: {access.decision.value}: {access.reason}"
        )

    checked_at = (now or (lambda: datetime.now(UTC)))()
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("authorization clock must return a timezone-aware datetime")
    state_identity = _access_state(
        access_profile,
        decision=access.decision,
        reason=access.reason,
    )
    resource_id = authorization_digest(
        "ceqanet-detail-resource",
        {"url": resolved_url},
    )
    exact_scope = _canonical_tuple(
        f"access-decision:{access.decision.value}",
        f"max-body-bytes:{max_body_bytes}",
        "method:GET",
        f"policy:{CEQANET_DETAIL_POLICY.policy_id}",
        f"timeout-seconds:{timeout_seconds:g}",
        f"url:{resolved_url}",
    )
    audit_identity = authorization_digest(
        "ceqanet-detail-audit",
        {
            "operator_id": operator_id,
            "action": _ACTION,
            "resource_id": resource_id,
            "exact_scope": exact_scope,
            "reason": authorization_reason,
            "state_identity": state_identity,
        },
    )
    decision = build_authorization_decision(
        actor_id=operator_id,
        action=_ACTION,
        resource_type=_RESOURCE_TYPE,
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("execute one exact read-only CEQAnet GET",),
        denied_authority=_canonical_tuple(
            "access-control bypass",
            "credential use",
            "persistence mutation",
            "production recurrence",
            "redirect following",
            "repeat execution",
            "source promotion",
        ),
        reason=authorization_reason,
        issued_at=checked_at,
        not_before=checked_at,
        expires_at=checked_at + _AUTHORIZATION_TTL,
        reuse_policy=AuthorizationReusePolicy.SINGLE_USE,
        revocation_identity=state_identity,
        audit_identity=audit_identity,
        caller_confirmation=True,
        limitations=_canonical_tuple(
            "local operator identity is not authentication",
            "no credential use or access-control bypass is authorized",
            "no persistence, source promotion, recurrence, or concurrent execution is authorized",
            "single local-process use only",
        ),
    )
    active_ledger = ledger or AuthorizationUseLedger()
    replay_identity = authorization_digest(
        "ceqanet-detail-attempt",
        {
            "decision_id": decision.decision_id,
            "resource_id": resource_id,
            "exact_scope": exact_scope,
        },
    )
    preflight = authorize_and_claim(
        decision,
        actor_id=operator_id,
        action=_ACTION,
        resource_type=_RESOURCE_TYPE,
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        current_revocation_identity=state_identity,
        replay_identity=replay_identity,
        checked_at=checked_at,
        ledger=active_ledger,
    )
    snapshot = (executor or execute_ceqanet_detail_request)(
        resolved_url,
        timeout_seconds=timeout_seconds,
        max_body_bytes=max_body_bytes,
    )
    reachable = snapshot.get("reachable") is True
    return {
        "metadata": {
            "schema_version": "ceqanet_detail_execution.v2",
            "allowed": True,
            "reason": "CEQAnet detail executor completed one authorized bounded read-only GET request.",
            "planned_request_count": 1,
            "executed_request_count": 1,
            "successful_response_count": int(reachable),
            "failed_response_count": int(not reachable),
            "access": {
                "decision": access.decision.value,
                "reason": access.reason,
                "state_identity": state_identity,
            },
            "authorization": {
                "decision_id": decision.decision_id,
                "preflight_id": preflight.preflight_id,
                "actor_id": decision.actor_id,
                "action": decision.action,
                "resource_id": decision.resource_id,
                "audit_identity": decision.audit_identity,
                "claim_audit_identity": preflight.audit_identity,
                "valid_until": preflight.valid_until.isoformat(),
                "granted_authority": list(decision.granted_authority),
                "denied_authority": list(decision.denied_authority),
                "limitations": list(decision.limitations),
            },
            "requested_url": resolved_url,
        },
        "snapshots": [snapshot],
    }
