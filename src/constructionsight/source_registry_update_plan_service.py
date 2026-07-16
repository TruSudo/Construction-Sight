"""Source registry update plan service."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.authorization_decision import AuthorizationUseLedger
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_promotion_plan_models import (
    SourcePromotionPlanAction,
    SourcePromotionPlanRow,
)
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_readiness_service import HttpReachabilityChecker
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
    SourceRegistryUpdatePlanRow,
)
from constructionsight.source_verification_checklist_models import SourceVerificationObservation
from constructionsight.source_verification_evidence_service import (
    build_source_verification_evidence_package,
)


def build_source_registry_update_plan(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    check_http: bool = False,
    http_checker: HttpReachabilityChecker | None = None,
    observations: Iterable[SourceVerificationObservation] | None = None,
) -> SourceRegistryUpdatePlanReport:
    """Build a dry-run registry update plan without writing registry files."""

    source_index = {source_registry_key(source): source for source in sources}
    promotion_plan = build_source_promotion_plan(
        sources,
        adapter_specs,
        check_http=check_http,
        http_checker=http_checker,
        observations=observations,
    )
    rows = [_update_row(row, source_index[row.source_key]) for row in promotion_plan.rows]
    return SourceRegistryUpdatePlanReport.from_rows(
        rows,
        registry_digest=source_registry_digest(sources),
    )


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
                observation.model_dump(mode="json")
                for observation in normalized_observations
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


def _update_row(
    plan_row: SourcePromotionPlanRow,
    source: PublicSource,
) -> SourceRegistryUpdatePlanRow:
    proposed_status = plan_row.proposed_registry_status
    original_payload = source.model_dump(mode="json")
    proposed_payload = _proposed_payload(original_payload, proposed_status)
    update_required = (
        proposed_status is not None
        and proposed_status != source.verification_status.value
    )
    return SourceRegistryUpdatePlanRow(
        source_key=plan_row.source_key,
        source_name=source.source_name,
        current_verification_status=source.verification_status.value,
        proposed_verification_status=proposed_status,
        planned_action=plan_row.planned_action.value,
        update_required=update_required,
        original_source_payload=original_payload,
        proposed_source_payload=proposed_payload if update_required else None,
        reasons=plan_row.reasons,
        limitations=_limitations(plan_row.limitations, update_required),
        evidence_refs=plan_row.evidence_refs,
        next_action=_next_action(plan_row.planned_action, update_required),
    )


def _proposed_payload(
    original_payload: dict[str, Any],
    proposed_status: str | None,
) -> dict[str, Any] | None:
    if proposed_status is None:
        return None
    proposed = dict(original_payload)
    proposed["verification_status"] = proposed_status
    return proposed


def _limitations(existing: list[str], update_required: bool) -> list[str]:
    limitations = [*existing, "dry-run only; source registry file is not modified"]
    if not update_required:
        limitations.append("no registry status change is proposed")
    return _unique(limitations)


def _next_action(action: SourcePromotionPlanAction, update_required: bool) -> str:
    if not update_required:
        return "complete evidence review before registry update planning"
    if action == SourcePromotionPlanAction.VERIFIED_CANDIDATE_REVIEW:
        return "review proposed verified status before any explicit apply workflow"
    if action == SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE:
        return "review proposed partial status before any explicit apply workflow"
    if action == SourcePromotionPlanAction.MARK_BLOCKED_CANDIDATE:
        return "review proposed blocked status before any explicit apply workflow"
    return "review proposed failed status before any explicit apply workflow"


def source_registry_key(source: PublicSource) -> str:
    """Return the canonical source key used across verification workflows."""

    evidence_package = build_source_verification_evidence_package([source], {}, check_http=False)
    return evidence_package.rows[0].source_key


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
