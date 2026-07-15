"""Scope-bound application service for a planned CEQAnet listing execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol

from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionError,
    CeqanetListingExecutionPolicy,
    execute_ceqanet_listing_plan,
)
from constructionsight.adapters.ceqanet_listing_models import (
    CeqanetListingExecutionResult,
    CeqanetListingPlan,
)
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
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access

_ACTION = "execute-ceqanet-listing-plan"
_RESOURCE_TYPE = "ceqanet-listing-plan"
_AUTHORIZATION_TTL = timedelta(minutes=5)
_POLICY = CeqanetListingExecutionPolicy(
    timeout_seconds=20.0,
    max_response_bytes=50_000,
    max_attempts=3,
    retry_delays_seconds=(0.25, 1.0),
)


class CeqanetListingServiceError(RuntimeError):
    """Raised when an authorized listing plan cannot complete transport execution."""


class CeqanetListingExecutor(Protocol):
    """Operation-specific listing transport interface."""

    def __call__(
        self,
        plan: CeqanetListingPlan,
        *,
        policy: CeqanetListingExecutionPolicy,
    ) -> CeqanetListingExecutionResult:
        """Execute one immutable listing plan."""


def _canonical_tuple(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=str.casefold))


def _access_state(
    profile: SourceAccessProfile,
    *,
    decision: AccessDecision,
    reason: str,
    plan: CeqanetListingPlan,
) -> str:
    return authorization_digest(
        "ceqanet-listing-access-state",
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
            "plan_id": plan.plan_id,
            "request_ids": [request.request_id for request in plan.requests],
        },
    )


def _verify_current_plan_access(
    plan: CeqanetListingPlan,
    *,
    decision: AccessDecision,
    reason: str,
) -> None:
    if decision is not AccessDecision.ALLOWED:
        raise AuthorizationDeniedError(
            f"lawful access preflight denied execution: {decision.value}: {reason}"
        )
    if any(
        request.access_decision is not decision
        or request.access_reason != reason
        or not request.access_allowed
        for request in plan.requests
    ):
        raise AuthorizationDeniedError(
            "current lawful-access state does not match the immutable listing plan"
        )


def execute_authorized_ceqanet_listing(
    *,
    plan: CeqanetListingPlan,
    access_profile: SourceAccessProfile,
    operator_id: str,
    authorization_reason: str,
    caller_confirmation: bool,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    executor: CeqanetListingExecutor | None = None,
) -> dict[str, object]:
    """Authorize and execute one exact immutable CEQAnet listing plan."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "caller confirmation is required in addition to scope-bound authority"
        )
    if not operator_id.strip() or operator_id != operator_id.strip():
        raise ValueError("operator_id must be nonblank and trimmed")
    if (
        not authorization_reason.strip()
        or authorization_reason != authorization_reason.strip()
    ):
        raise ValueError("authorization_reason must be nonblank and trimmed")
    if not plan.requests or plan.request_count != len(plan.requests):
        raise ValueError("listing plan must contain its exact nonempty request sequence")

    access = evaluate_access(access_profile)
    _verify_current_plan_access(
        plan,
        decision=access.decision,
        reason=access.reason,
    )
    checked_at = (now or (lambda: datetime.now(UTC)))()
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("authorization clock must return a timezone-aware datetime")
    state_identity = _access_state(
        access_profile,
        decision=access.decision,
        reason=access.reason,
        plan=plan,
    )
    exact_scope = _canonical_tuple(
        f"county:{plan.county}",
        f"max-attempts:{_POLICY.max_attempts}",
        f"max-pages:{plan.max_pages}",
        f"max-response-bytes:{_POLICY.max_response_bytes}",
        "method:GET",
        f"plan-id:{plan.plan_id}",
        "policy:CS-NET-002",
        f"request-count:{plan.request_count}",
        *(
            f"request-id:{request.request_id}"
            for request in plan.requests
        ),
        f"timeout-seconds:{_POLICY.timeout_seconds:g}",
    )
    audit_identity = authorization_digest(
        "ceqanet-listing-audit",
        {
            "operator_id": operator_id,
            "action": _ACTION,
            "plan_id": plan.plan_id,
            "exact_scope": exact_scope,
            "reason": authorization_reason,
            "state_identity": state_identity,
        },
    )
    decision = build_authorization_decision(
        actor_id=operator_id,
        action=_ACTION,
        resource_type=_RESOURCE_TYPE,
        resource_id=plan.plan_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("execute the exact immutable CEQAnet listing plan",),
        denied_authority=_canonical_tuple(
            "access-control bypass",
            "credential use",
            "page-count expansion",
            "persistence mutation",
            "production recurrence",
            "query mutation",
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
            "no persistence, promotion, recurrence, or concurrent execution is authorized",
            "partial page results remain incomplete evidence",
            "single local-process use only",
        ),
    )
    active_ledger = ledger or AuthorizationUseLedger()
    preflight = authorize_and_claim(
        decision,
        actor_id=operator_id,
        action=_ACTION,
        resource_type=_RESOURCE_TYPE,
        resource_id=plan.plan_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        current_revocation_identity=state_identity,
        replay_identity=authorization_digest(
            "ceqanet-listing-attempt",
            {
                "decision_id": decision.decision_id,
                "plan_id": plan.plan_id,
                "request_ids": [request.request_id for request in plan.requests],
            },
        ),
        checked_at=checked_at,
        ledger=active_ledger,
    )
    try:
        result = (executor or execute_ceqanet_listing_plan)(
            plan,
            policy=_POLICY,
        )
    except CeqanetListingExecutionError as exc:
        raise CeqanetListingServiceError(str(exc)) from exc

    payload = result.to_dict()
    payload["authorization"] = {
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
        "access_state_identity": state_identity,
    }
    return payload
