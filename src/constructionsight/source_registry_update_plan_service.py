"""Source registry update plan service."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_promotion_plan_models import (
    SourcePromotionPlanAction,
    SourcePromotionPlanReport,
    SourcePromotionPlanRow,
)
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
    SourceRegistryUpdatePlanRow,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.source_verification_evidence_service import (
    build_source_verification_evidence_package,
)


def build_source_registry_update_plan(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    check_http: bool = False,
    observations: Iterable[SourceVerificationObservation] | None = None,
) -> SourceRegistryUpdatePlanReport:
    """Build a dry-run registry update plan without writing registry files."""

    promotion_plan = build_source_promotion_plan(
        sources,
        adapter_specs,
        check_http=check_http,
        observations=observations,
    )
    return _build_source_registry_update_plan_from_promotion_plan(
        sources,
        promotion_plan,
    )


def _build_source_registry_update_plan_from_promotion_plan(
    sources: list[PublicSource],
    promotion_plan: SourcePromotionPlanReport,
) -> SourceRegistryUpdatePlanReport:
    source_index = {source_registry_key(source): source for source in sources}
    rows = [
        _update_row(row, source_index[row.source_key]) for row in promotion_plan.rows
    ]
    return SourceRegistryUpdatePlanReport.from_rows(
        rows,
        registry_digest=source_registry_digest(sources),
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

    evidence_package = build_source_verification_evidence_package(
        [source],
        {},
        check_http=False,
    )
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
