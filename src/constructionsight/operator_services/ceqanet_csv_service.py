"""Scope-bound application facade for one CEQAnet CSV evidence request."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_csv_live_models import (
    CeqanetCsvLiveExecution,
    CeqanetCsvLiveVerification,
)
from constructionsight.ceqanet_csv_live_service import (
    execute_ceqanet_csv_live_request,
    verify_ceqanet_csv_live_execution,
)
from constructionsight.ceqanet_csv_models import CeqanetCsvExportRequest
from constructionsight.ceqanet_csv_service import parse_ceqanet_csv_export_url
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)

_ACTION = "execute-ceqanet-csv-evidence-request"
_RESOURCE_TYPE = "public-ceqanet-csv-export"
_POLICY_ID = "CS-NET-003"
_MAX_TIMEOUT_SECONDS = 20.0
_MAX_BODY_BYTES = 10_000_000
_MAX_RETAINED_ROWS = 1_000


@dataclass(frozen=True)
class AuthorizedCeqanetCsvExecution:
    """One authorized execution, its verification, and its authority evidence."""

    execution: CeqanetCsvLiveExecution
    verification: CeqanetCsvLiveVerification
    authorization: LocalAuthorizationResult


def _canonical_tuple(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=str.casefold))


def _access_state(
    request: CeqanetCsvExportRequest,
    profile: SourceAccessProfile,
    *,
    decision: AccessDecision,
    reason: str,
    timeout_seconds: float,
    max_body_bytes: int,
    max_retained_rows: int,
) -> str:
    return authorization_digest(
        "ceqanet-csv-access-state",
        {
            "request": request.model_dump(mode="json"),
            "public_url": profile.public_url,
            "requires_login": profile.requires_login,
            "has_captcha": profile.has_captcha,
            "robots_disallows_collection": profile.robots_disallows_collection,
            "terms_disallow_collection": profile.terms_disallow_collection,
            "paywalled": profile.paywalled,
            "rate_limit_known": profile.rate_limit_known,
            "rate_limit_notes": profile.rate_limit_notes,
            "access_decision": decision.value,
            "access_reason": reason,
            "policy_id": _POLICY_ID,
            "timeout_seconds": timeout_seconds,
            "max_body_bytes": max_body_bytes,
            "max_retained_rows": max_retained_rows,
        },
    )


def verify_retained_ceqanet_csv(
    execution: CeqanetCsvLiveExecution,
) -> CeqanetCsvLiveVerification:
    """Verify retained CSV evidence through the application boundary."""

    return verify_ceqanet_csv_live_execution(execution)


def execute_authorized_ceqanet_csv(
    *,
    request: CeqanetCsvExportRequest,
    access_profile: SourceAccessProfile,
    authorization_reason: str,
    caller_confirmation: bool,
    timeout_seconds: float,
    max_body_bytes: int,
    max_retained_rows: int,
    operator_id: str | None = None,
) -> AuthorizedCeqanetCsvExecution:
    """Authorize, execute, and independently verify one exact CSV GET."""

    canonical_request = parse_ceqanet_csv_export_url(request.source_url)
    if canonical_request != request:
        raise ValueError("CEQAnet CSV request fields do not agree with source_url")
    if timeout_seconds <= 0 or timeout_seconds > _MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout_seconds cannot exceed the declared CS-NET-003 ceiling")
    if max_body_bytes < 1 or max_body_bytes > _MAX_BODY_BYTES:
        raise ValueError("max_body_bytes cannot exceed the declared CS-NET-003 ceiling")
    if max_retained_rows < 0 or max_retained_rows > _MAX_RETAINED_ROWS:
        raise ValueError("max_retained_rows must be between 0 and 1000")

    access = evaluate_access(access_profile)
    if access.decision is not AccessDecision.ALLOWED:
        raise AuthorizationDeniedError(
            "lawful access preflight denied execution: "
            f"{access.decision.value}: {access.reason}"
        )

    state_identity = _access_state(
        request,
        access_profile,
        decision=access.decision,
        reason=access.reason,
        timeout_seconds=timeout_seconds,
        max_body_bytes=max_body_bytes,
        max_retained_rows=max_retained_rows,
    )
    resource_id = authorization_digest(
        "ceqanet-csv-resource",
        {"source_url": request.source_url},
    )
    exact_scope = _canonical_tuple(
        f"access-decision:{access.decision.value}",
        f"max-body-bytes:{max_body_bytes}",
        f"max-retained-rows:{max_retained_rows}",
        "method:GET",
        f"policy:{_POLICY_ID}",
        "redirects:denied",
        "retries:0",
        f"timeout-seconds:{timeout_seconds:g}",
        f"url:{request.source_url}",
    )
    authorization = authorize_local_operator_operation(
        action=_ACTION,
        resource_type=_RESOURCE_TYPE,
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "execute one exact read-only CEQAnet CSV evidence GET",
        ),
        denied_authority=_canonical_tuple(
            "access-control bypass",
            "attachment download",
            "credential use",
            "persistence mutation",
            "production recurrence",
            "redirect following",
            "repeat execution",
            "request mutation",
            "retry",
            "source promotion",
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=_canonical_tuple(
            "local operator identity is not authentication",
            "no document attachment download is authorized",
            "no persistence, promotion, recurrence, or retry is authorized",
            "one durable exact-request allowance across processes",
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )
    def execute(
        trusted_at: datetime,
    ) -> tuple[CeqanetCsvLiveExecution, CeqanetCsvLiveVerification]:
        execution = execute_ceqanet_csv_live_request(
            request,
            execute_live=True,
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
            max_retained_rows=max_retained_rows,
            executed_at=trusted_at,
        )
        return execution, verify_ceqanet_csv_live_execution(execution)

    execution, verification = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "ceqanet-csv-manual-allowance",
            {"state_identity": state_identity},
        ),
        content_identity=state_identity,
        implementation_id=(
            "constructionsight.ceqanet_csv_live_service."
            "execute_ceqanet_csv_live_request"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=lambda result: {
            "execution": result[0].model_dump(mode="json"),
            "verification": result[1].model_dump(mode="json"),
        },
        decode_result=lambda payload: (
            CeqanetCsvLiveExecution.model_validate(payload["execution"]),
            CeqanetCsvLiveVerification.model_validate(payload["verification"]),
        ),
    )
    return AuthorizedCeqanetCsvExecution(
        execution=execution,
        verification=verification,
        authorization=authorization,
    )
