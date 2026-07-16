"""Scope-bound application facade for source-registry planning and apply."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.authorization_decision import AuthorizationUseLedger
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_readiness_service import HttpReachabilityChecker
from constructionsight.source_registry_apply_models import SourceRegistryApplyReport
from constructionsight.source_registry_apply_service import apply_source_registry_update_plan
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
)
from constructionsight.source_registry_update_plan_service import (
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import SourceVerificationObservation


@dataclass(frozen=True)
class AuthorizedSourceRegistryApplyResult:
    """In-memory registry result and its consumed scope-bound authorization."""

    sources: tuple[PublicSource, ...]
    report: SourceRegistryApplyReport
    authorization: LocalAuthorizationResult


def build_authorized_source_registry_update_plan(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    observations: Iterable[SourceVerificationObservation] | None,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
    http_checker: HttpReachabilityChecker | None = None,
) -> SourceRegistryUpdatePlanReport:
    """Authorize exact-source HTTP evidence used to build one report-only plan."""

    normalized_observations = tuple(observations or ())
    registry_identity = source_registry_digest(sources)
    state_identity = authorization_digest(
        "source-registry-plan-state",
        {
            "registry_digest": registry_identity,
            "sources": [source.model_dump(mode="json") for source in sources],
            "adapter_specs": [
                {
                    "platform_family": family.value,
                    "status": spec.status.value,
                    "uses_public_http": spec.uses_public_http,
                }
                for family, spec in sorted(
                    adapter_specs.items(),
                    key=lambda item: item[0].value,
                )
            ],
            "observations": [
                observation.model_dump(mode="json") for observation in normalized_observations
            ],
            "network_policy": "CS-NET-008",
        },
    )
    exact_scope = tuple(
        sorted(
            {
                "concurrency:1",
                "max-attempts-per-source:1",
                "max-response-bytes:50000",
                "method:GET",
                f"observation-count:{len(normalized_observations)}",
                "output:report-only-update-plan",
                "policy:CS-NET-008",
                "redirects:denied",
                f"registry-digest:{registry_identity}",
                "retries:0",
                f"source-count:{len(sources)}",
                *(f"url:{source.public_url}" for source in sources),
            },
            key=str.casefold,
        )
    )
    authorize_local_operator_operation(
        action="build-source-registry-update-plan-live-evidence",
        resource_type="public-source-registry-snapshot",
        resource_id=registry_identity,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "perform one bounded verification GET per source and build a report-only update plan",
        ),
        denied_authority=tuple(
            sorted(
                {
                    "access-control bypass",
                    "alternate-host fallback",
                    "automatic registry mutation",
                    "credential use",
                    "document download",
                    "observation mutation",
                    "persistence mutation",
                    "production recurrence",
                    "redirect following",
                    "retry",
                    "source promotion",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=tuple(
            sorted(
                {
                    "a generated plan is not authority to apply registry changes",
                    "HTTP evidence does not replace manual verification observations",
                    "local operator identity is not authentication",
                    "single local-process use only",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
        now=now,
        ledger=ledger,
    )
    return build_source_registry_update_plan(
        sources,
        adapter_specs,
        check_http=True,
        http_checker=http_checker,
        observations=normalized_observations,
    )


def apply_authorized_source_registry_update_plan(
    sources: list[PublicSource],
    plan: SourceRegistryUpdatePlanReport,
    *,
    expected_plan_digest: str,
    expected_registry_digest: str,
    target_path_identity: str,
    caller_confirmation: bool,
    authorization_reason: str,
    operator_id: str | None = None,
    now: Callable[[], datetime] | None = None,
    ledger: AuthorizationUseLedger | None = None,
) -> AuthorizedSourceRegistryApplyResult:
    """Authorize and apply one exact reviewed registry plan in memory."""

    target_identity = target_path_identity.strip()
    if not target_identity:
        raise ValueError("target_path_identity must be nonblank")
    if expected_plan_digest != plan.plan_digest:
        raise ValueError("expected plan digest does not match reviewed plan")
    current_registry_digest = source_registry_digest(sources)
    if expected_registry_digest != current_registry_digest:
        raise ValueError("expected registry digest does not match current registry")

    current_state_identity = authorization_digest(
        "source-registry-apply-state",
        {
            "sources": [source.model_dump(mode="json") for source in sources],
            "plan": plan.model_dump(mode="json"),
            "expected_plan_digest": expected_plan_digest,
            "expected_registry_digest": expected_registry_digest,
            "target_path_identity": target_identity,
        },
    )
    resource_id = authorization_digest(
        "source-registry-apply-resource",
        {
            "plan_digest": expected_plan_digest,
            "registry_digest": expected_registry_digest,
            "target_path_identity": target_identity,
        },
    )
    exact_scope = tuple(
        sorted(
            {
                "allowed-field:verification_status",
                "audit-before-success-required:true",
                f"plan-digest:{expected_plan_digest}",
                f"registry-digest:{expected_registry_digest}",
                "replacement:atomic",
                f"target-path:{target_identity}",
                f"update-count:{plan.update_count}",
            },
            key=str.casefold,
        )
    )
    authorization = authorize_local_operator_operation(
        action="apply-source-registry-update-plan",
        resource_type="source-registry-update-plan",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=current_state_identity,
        expected_identity=current_state_identity,
        granted_authority=(
            "apply the exact reviewed verification-status transitions to one exact registry target",
        ),
        denied_authority=tuple(
            sorted(
                {
                    "changing source identity",
                    "changing fields other than verification_status",
                    "destructive overwrite without atomic replacement",
                    "network execution",
                    "partial registry mutation",
                    "plan substitution",
                    "registry substitution",
                    "source deletion",
                    "unreviewed status promotion",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=caller_confirmation,
        limitations=tuple(
            sorted(
                {
                    "authorization covers one local-process in-memory apply result",
                    "caller must persist only the returned registry and report to the bound target",
                    "local operator identity is not authentication",
                    "single local-process use only",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=current_state_identity,
        now=now,
        ledger=ledger,
    )
    updated_sources, report = apply_source_registry_update_plan(
        sources,
        plan,
        approved_plan_digest=expected_plan_digest,
    )
    return AuthorizedSourceRegistryApplyResult(
        sources=tuple(updated_sources),
        report=report,
        authorization=authorization,
    )
