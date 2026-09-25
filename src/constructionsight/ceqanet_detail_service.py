"""Scope-bound application service for one CEQAnet detail-page read."""

from __future__ import annotations

from urllib.parse import urlsplit

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_detail_http import (
    CEQANET_DETAIL_POLICY,
    execute_ceqanet_detail_request,
)
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)

_ACTION = "execute-ceqanet-detail-read"
_RESOURCE_TYPE = "public-ceqanet-detail-page"
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
            "access_fact_basis": profile.access_fact_basis,
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
) -> dict[str, object]:
    """Authorize and execute one exact CEQAnet GET without persistence or retry."""

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
    if (
        timeout_seconds <= 0
        or timeout_seconds > CEQANET_DETAIL_POLICY.read_timeout_seconds
    ):
        raise ValueError(
            "timeout_seconds cannot exceed the declared CS-NET-006 ceiling"
        )
    if (
        max_body_bytes < 1
        or max_body_bytes > CEQANET_DETAIL_POLICY.max_response_bytes
    ):
        raise ValueError(
            "max_body_bytes cannot exceed the declared CS-NET-006 ceiling"
        )

    resolved_url = _validated_detail_url(detail_url)
    access = evaluate_access(access_profile)
    if access.decision is not AccessDecision.ALLOWED:
        raise AuthorizationDeniedError(
            "lawful access preflight denied execution: "
            f"{access.decision.value}: {access.reason}"
        )

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
    authorization = authorize_local_operator_operation(
        operator_id=operator_id,
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
        caller_confirmation=True,
        limitations=_canonical_tuple(
            "local operator identity is not authentication",
            "no credential use or access-control bypass is authorized",
            (
                "no persistence, source promotion, recurrence, or concurrent "
                "execution is authorized"
            ),
            "one durable exact-request allowance across processes",
        ),
        current_revocation_identity=state_identity,
    )

    def execute(_trusted_at: object) -> dict[str, object]:
        snapshot = execute_ceqanet_detail_request(
            resolved_url,
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
        )
        reachable = snapshot.get("reachable") is True
        return {
        "metadata": {
            "schema_version": "ceqanet_detail_execution.v2",
            "allowed": True,
            "reason": (
                "CEQAnet detail executor completed one authorized bounded "
                "read-only GET request."
            ),
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
                "decision_id": authorization.decision.decision_id,
                "preflight_id": authorization.preflight.preflight_id,
                "actor_id": authorization.decision.actor_id,
                "action": authorization.decision.action,
                "resource_id": authorization.decision.resource_id,
                "audit_identity": authorization.decision.audit_identity,
                "claim_audit_identity": authorization.preflight.audit_identity,
                "valid_until": authorization.preflight.valid_until.isoformat(),
                "granted_authority": list(authorization.decision.granted_authority),
                "denied_authority": list(authorization.decision.denied_authority),
                "limitations": list(authorization.decision.limitations),
            },
            "requested_url": resolved_url,
        },
        "snapshots": [snapshot],
    }

    return _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "ceqanet-detail-manual-allowance",
            {"resource_id": resource_id, "state_identity": state_identity},
        ),
        content_identity=state_identity,
        implementation_id=(
            "constructionsight.ceqanet_detail_http.execute_ceqanet_detail_request"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda result: result,
        decode_result=lambda payload: dict(payload),
    )
