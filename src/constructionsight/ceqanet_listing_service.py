"""Scope-bound application service for a planned CEQAnet listing execution."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from constructionsight.adapters.ceqanet_listing import CeqanetListingPlan
from constructionsight.adapters.ceqanet_listing_dry_run import CeqanetListingDryRunExecutor
from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionError,
    CeqanetListingExecutionPolicy,
    CeqanetListingExecutionReport,
    execute_ceqanet_listing_plan,
)
from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)

_ACTION = "execute-ceqanet-listing-plan"
_RESOURCE_TYPE = "ceqanet-listing-plan"


class CeqanetListingServiceError(RuntimeError):
    """Raised when an authorized listing plan cannot complete transport execution."""


class CeqanetListingExecutor(Protocol):
    """Operation-specific listing transport interface."""

    def __call__(
        self,
        plan: CeqanetListingPlan,
        *,
        policy: CeqanetListingExecutionPolicy,
    ) -> CeqanetListingExecutionReport:
        """Execute one immutable listing plan."""


def _canonical_tuple(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=str.casefold))


def _plan_identity(plan: CeqanetListingPlan) -> str:
    dry_run = CeqanetListingDryRunExecutor().run(plan)
    return authorization_digest(
        "ceqanet-listing-plan",
        {
            "query": {
                "counties": list(plan.query.counties),
                "document_types": list(plan.query.document_types),
                "lead_agencies": list(plan.query.lead_agencies),
                "text_terms": list(plan.query.text_terms),
                "received_from": (
                    plan.query.received_from.isoformat()
                    if plan.query.received_from is not None
                    else None
                ),
                "received_to": (
                    plan.query.received_to.isoformat()
                    if plan.query.received_to is not None
                    else None
                ),
                "posted_from": (
                    plan.query.posted_from.isoformat()
                    if plan.query.posted_from is not None
                    else None
                ),
                "posted_to": (
                    plan.query.posted_to.isoformat()
                    if plan.query.posted_to is not None
                    else None
                ),
                "high_signal_only": plan.query.high_signal_only,
                "page_size": plan.query.page_size,
                "max_pages": plan.query.max_pages,
            },
            "access_decision": plan.access_result.decision.value,
            "access_reason": plan.access_result.reason,
            "reason": plan.reason,
            "requests": [
                {
                    "page_number": request.page_number,
                    "method": request.method,
                    "url": request.url,
                    "params": list(request.params),
                    "downloads_documents": request.downloads_documents,
                    "mutates_remote_state": request.mutates_remote_state,
                }
                for request in dry_run.requests
            ],
        },
    )


def _access_state(
    profile: SourceAccessProfile,
    *,
    decision: AccessDecision,
    reason: str,
    plan_id: str,
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
            "plan_id": plan_id,
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
    if (
        plan.access_result.decision is not decision
        or plan.access_result.reason != reason
        or not plan.allowed
    ):
        raise AuthorizationDeniedError(
            "current lawful-access state does not match the immutable listing plan"
        )


def _report_payload(
    report: CeqanetListingExecutionReport,
    *,
    plan: CeqanetListingPlan,
    authorization: LocalAuthorizationResult,
    plan_id: str,
    state_identity: str,
) -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_listing_execution.v2",
            "allowed": report.allowed,
            "reason": report.reason,
            "planned_request_count": report.planned_request_count,
            "executed_request_count": report.executed_request_count,
            "successful_response_count": report.successful_response_count,
            "failed_response_count": report.failed_response_count,
            "maximum_records": report.maximum_records,
            "plan_id": plan_id,
            "access": {
                "decision": plan.access_result.decision.value,
                "reason": plan.access_result.reason,
                "state_identity": state_identity,
            },
            "authorization": authorization.to_dict(),
        },
        "snapshots": [
            {
                "page_number": snapshot.page_number,
                "method": snapshot.method,
                "request_url": snapshot.request_url,
                "final_url": snapshot.final_url,
                "status_code": snapshot.status_code,
                "content_type": snapshot.content_type,
                "body_text": snapshot.body_text,
                "body_length": snapshot.body_length,
                "body_truncated": snapshot.body_truncated,
                "executed": snapshot.executed,
                "error": snapshot.error,
                "failure_kind": snapshot.failure_kind,
                "reachable": snapshot.reachable,
            }
            for snapshot in report.snapshots
        ],
    }


def execute_authorized_ceqanet_listing(
    *,
    plan: CeqanetListingPlan,
    access_profile: SourceAccessProfile,
    authorization_reason: str,
    caller_confirmation: bool,
    timeout_seconds: float = 20.0,
    max_response_bytes: int = 50_000,
    operator_id: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    executor: CeqanetListingExecutor | None = None,
) -> dict[str, object]:
    """Authorize and execute one exact immutable CEQAnet listing plan."""

    if not caller_confirmation:
        raise AuthorizationDeniedError(
            "caller confirmation is required in addition to scope-bound authority"
        )
    access = evaluate_access(access_profile)
    _verify_current_plan_access(
        plan,
        decision=access.decision,
        reason=access.reason,
    )
    policy = CeqanetListingExecutionPolicy(
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
    )
    dry_run = CeqanetListingDryRunExecutor().run(plan)
    if not dry_run.requests or dry_run.planned_request_count != len(dry_run.requests):
        raise ValueError("listing plan must contain its exact nonempty request sequence")
    if dry_run.downloads_documents or dry_run.mutates_remote_state:
        raise AuthorizationDeniedError(
            "listing plan attempts an authority outside read-only listing"
        )

    plan_id = _plan_identity(plan)
    state_identity = _access_state(
        access_profile,
        decision=access.decision,
        reason=access.reason,
        plan_id=plan_id,
    )
    exact_scope = _canonical_tuple(
        f"max-attempts:{policy.max_attempts}",
        f"max-pages:{plan.query.max_pages}",
        f"max-response-bytes:{policy.max_response_bytes}",
        "method:GET",
        f"plan-id:{plan_id}",
        "policy:CS-NET-002",
        f"request-count:{dry_run.planned_request_count}",
        "retries:0",
        f"timeout-seconds:{policy.timeout_seconds:g}",
        *(f"url:{request.url}" for request in dry_run.requests),
    )
    authorization = authorize_local_operator_operation(
        action=_ACTION,
        resource_type=_RESOURCE_TYPE,
        resource_id=plan_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("execute the exact immutable CEQAnet listing plan",),
        denied_authority=_canonical_tuple(
            "access-control bypass",
            "credential use",
            "document download",
            "page-count expansion",
            "persistence mutation",
            "production recurrence",
            "query mutation",
            "redirect following",
            "repeat execution",
            "retry",
            "source promotion",
        ),
        reason=authorization_reason,
        caller_confirmation=True,
        limitations=_canonical_tuple(
            "local operator identity is not authentication",
            "no credential use or access-control bypass is authorized",
            "no persistence, promotion, recurrence, retry, or concurrent execution is authorized",
            "partial page results remain incomplete evidence",
            "single local-process use only",
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
        now=now,
        ledger=ledger,
    )
    active_executor: CeqanetListingExecutor = executor or execute_ceqanet_listing_plan
    try:
        report = active_executor(plan, policy=policy)
    except CeqanetListingExecutionError as exc:
        raise CeqanetListingServiceError(str(exc)) from exc
    return _report_payload(
        report,
        plan=plan,
        authorization=authorization,
        plan_id=plan_id,
        state_identity=state_identity,
    )
