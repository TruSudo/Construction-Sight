"""Scope-bound application facade for live source-promotion planning."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.authorization_decision import AuthorizationUseLedger
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.local_operator_authorization import authorize_local_operator_operation
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_promotion_plan_models import SourcePromotionPlanReport
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_readiness_service import HttpReachabilityChecker
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.source_verification_checklist_models import SourceVerificationObservation


def build_authorized_source_promotion_plan(
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
) -> SourcePromotionPlanReport:
    """Authorize exact-source HTTP evidence used by one report-only promotion plan."""

    normalized_observations = tuple(observations or ())
    registry_identity = source_registry_digest(sources)
    state_identity = authorization_digest(
        "source-promotion-plan-state",
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
                "output:report-only-promotion-plan",
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
        action="build-source-promotion-plan-live-evidence",
        resource_type="public-source-registry-snapshot",
        resource_id=registry_identity,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=(
            "perform one bounded verification GET per source and build a "
            "report-only promotion plan",
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
    return build_source_promotion_plan(
        sources,
        adapter_specs,
        check_http=True,
        http_checker=http_checker,
        observations=normalized_observations,
    )
