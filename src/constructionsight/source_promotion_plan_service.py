"""Source promotion plan service."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_promotion_plan_models import (
    SourcePromotionPlanAction,
    SourcePromotionPlanReport,
    SourcePromotionPlanRow,
)
from constructionsight.source_readiness_service import HttpReachabilityChecker
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistRow,
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_source_verification_checklist_report,
)


def build_source_promotion_plan(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    check_http: bool = False,
    http_checker: HttpReachabilityChecker | None = None,
    observations: Iterable[SourceVerificationObservation] | None = None,
) -> SourcePromotionPlanReport:
    """Build a dry-run source promotion plan without mutating registry data."""

    checklist = build_source_verification_checklist_report(
        sources,
        adapter_specs,
        check_http=check_http,
        http_checker=http_checker,
        observations=observations,
    )
    return SourcePromotionPlanReport.from_rows([_plan_row(row) for row in checklist.rows])


def _plan_row(row: SourceVerificationChecklistRow) -> SourcePromotionPlanRow:
    action = _planned_action(row)
    return SourcePromotionPlanRow(
        source_key=row.source_key,
        source_name=row.source_name,
        platform_family=row.platform_family,
        original_url=row.original_url,
        final_url=row.final_url,
        registry_status=row.registry_status,
        adapter_status=row.adapter_status,
        readiness_status=row.readiness_status,
        checklist_status=row.checklist_status.value,
        planned_action=action,
        proposed_registry_status=_proposed_registry_status(action),
        reasons=_unique([*row.reasons, *_plan_reasons(row, action)]),
        limitations=_unique([*row.limitations, *_plan_limitations(row, action)]),
        evidence_refs=row.evidence_refs,
        next_action=_next_action(action),
    )


def _planned_action(row: SourceVerificationChecklistRow) -> SourcePromotionPlanAction:
    if row.access_barrier == ChecklistItemStatus.BLOCKED:
        return SourcePromotionPlanAction.MARK_BLOCKED_CANDIDATE
    if row.checklist_status.value == "failed":
        return SourcePromotionPlanAction.MARK_FAILED_CANDIDATE
    if _has_full_manual_verification(row):
        if row.adapter_status == "placeholder":
            return SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE
        return SourcePromotionPlanAction.VERIFIED_CANDIDATE_REVIEW
    if _has_partial_manual_verification(row):
        return SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE
    return SourcePromotionPlanAction.KEEP_UNVERIFIED


def _has_full_manual_verification(row: SourceVerificationChecklistRow) -> bool:
    return (
        row.public_entry_page == ChecklistItemStatus.OBSERVED
        and row.query_behavior == ChecklistItemStatus.OBSERVED
        and row.result_list == ChecklistItemStatus.OBSERVED
        and row.detail_page == ChecklistItemStatus.OBSERVED
        and row.access_barrier == ChecklistItemStatus.NOT_OBSERVED
        and row.terms_review == ChecklistItemStatus.OBSERVED
        and bool(row.evidence_refs)
    )


def _has_partial_manual_verification(row: SourceVerificationChecklistRow) -> bool:
    return (
        row.query_behavior == ChecklistItemStatus.OBSERVED
        or row.result_list == ChecklistItemStatus.OBSERVED
        or row.detail_page == ChecklistItemStatus.OBSERVED
        or row.terms_review == ChecklistItemStatus.OBSERVED
    )


def _proposed_registry_status(action: SourcePromotionPlanAction) -> str | None:
    if action == SourcePromotionPlanAction.MARK_BLOCKED_CANDIDATE:
        return "blocked"
    if action == SourcePromotionPlanAction.MARK_FAILED_CANDIDATE:
        return "failed"
    if action == SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE:
        return "partial"
    if action == SourcePromotionPlanAction.VERIFIED_CANDIDATE_REVIEW:
        return "verified"
    return None


def _plan_reasons(
    row: SourceVerificationChecklistRow,
    action: SourcePromotionPlanAction,
) -> list[str]:
    if action == SourcePromotionPlanAction.KEEP_UNVERIFIED:
        return ["checklist evidence is insufficient for registry status change"]
    if action == SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE:
        return ["some manual source behavior was observed"]
    if action == SourcePromotionPlanAction.VERIFIED_CANDIDATE_REVIEW:
        return [
            "manual entry, query, list, detail, barrier, terms, and evidence review is complete"
        ]
    if action == SourcePromotionPlanAction.MARK_BLOCKED_CANDIDATE:
        return ["operator observed an access barrier"]
    return [f"checklist status is {row.checklist_status.value}"]


def _plan_limitations(
    row: SourceVerificationChecklistRow,
    action: SourcePromotionPlanAction,
) -> list[str]:
    limitations: list[str] = []
    if action != SourcePromotionPlanAction.KEEP_UNVERIFIED:
        limitations.append("this is a dry-run plan and does not mutate registry data")
    if action == SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE:
        limitations.append("source evidence is incomplete or adapter maturity is limited")
    if action == SourcePromotionPlanAction.VERIFIED_CANDIDATE_REVIEW:
        limitations.append("human approval is still required before registry update")
    if not row.evidence_refs:
        limitations.append("no evidence references were supplied")
    return limitations


def _next_action(action: SourcePromotionPlanAction) -> str:
    if action == SourcePromotionPlanAction.KEEP_UNVERIFIED:
        return "complete checklist observations before source update planning"
    if action == SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE:
        return "review partial candidate before any registry update"
    if action == SourcePromotionPlanAction.VERIFIED_CANDIDATE_REVIEW:
        return "review verified candidate before any registry update"
    if action == SourcePromotionPlanAction.MARK_BLOCKED_CANDIDATE:
        return "review blocked candidate before any registry update"
    return "review failed candidate before any registry update"


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
