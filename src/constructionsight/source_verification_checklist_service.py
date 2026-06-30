"""Source verification checklist service."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistReport,
    SourceVerificationChecklistRow,
    SourceVerificationChecklistStatus,
    SourceVerificationObservation,
)
from constructionsight.source_verification_evidence_service import (
    HttpReachabilityChecker,
    build_source_verification_evidence_package,
)


def build_source_verification_checklist_report(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    check_http: bool = False,
    http_checker: HttpReachabilityChecker | None = None,
    observations: Iterable[SourceVerificationObservation] | None = None,
) -> SourceVerificationChecklistReport:
    """Build a report-only manual source-verification checklist."""

    observation_index = _observation_index(observations or [])
    evidence_package = build_source_verification_evidence_package(
        sources,
        adapter_specs,
        check_http=check_http,
        http_checker=http_checker,
    )
    rows = [
        _build_row(
            source_key=row.source_key,
            source_name=row.source_name,
            platform_family=row.platform_family,
            original_url=row.original_url,
            final_url=row.final_url,
            http_status_code=row.http_status_code,
            redirect_classification=row.redirect_classification.value,
            registry_status=row.verification_status,
            adapter_status=row.adapter_status,
            readiness_status=row.readiness_status,
            recommendation=row.recommendation.value,
            reasons=row.reasons,
            limitations=row.limitations,
            observation=observation_index.get(row.source_key)
            or observation_index.get(row.source_name),
        )
        for row in evidence_package.rows
    ]
    return SourceVerificationChecklistReport.from_rows(rows)


def _build_row(
    *,
    source_key: str,
    source_name: str,
    platform_family: str,
    original_url: str,
    final_url: str | None,
    http_status_code: int | None,
    redirect_classification: str,
    registry_status: str,
    adapter_status: str,
    readiness_status: str,
    recommendation: str,
    reasons: list[str],
    limitations: list[str],
    observation: SourceVerificationObservation | None,
) -> SourceVerificationChecklistRow:
    public_entry_page = _item_from_bool(
        observation.public_entry_observed if observation else None,
        default=ChecklistItemStatus.OBSERVED if readiness_status == "reachable" else None,
    )
    query_behavior = _item_from_bool(observation.query_behavior_observed if observation else None)
    result_list = _item_from_bool(observation.result_list_observed if observation else None)
    detail_page = _item_from_bool(observation.detail_page_observed if observation else None)
    access_barrier = _access_barrier_status(observation)
    terms_review = _item_from_bool(observation.terms_review_observed if observation else None)
    checklist_status = _checklist_status(
        public_entry_page,
        query_behavior,
        result_list,
        detail_page,
        access_barrier,
    )
    return SourceVerificationChecklistRow(
        source_key=source_key,
        source_name=source_name,
        platform_family=platform_family,
        original_url=original_url,
        final_url=final_url,
        http_status_code=http_status_code,
        redirect_classification=redirect_classification,
        registry_status=registry_status,
        adapter_status=adapter_status,
        readiness_status=readiness_status,
        checklist_status=checklist_status,
        public_entry_page=public_entry_page,
        query_behavior=query_behavior,
        result_list=result_list,
        detail_page=detail_page,
        access_barrier=access_barrier,
        terms_review=terms_review,
        recommendation=recommendation,
        reasons=_unique([*reasons, *_observation_reasons(observation)]),
        limitations=_unique([*limitations, *_checklist_limitations(checklist_status)]),
        next_action=_next_action(checklist_status),
        observation_notes=observation.notes if observation else None,
        evidence_refs=observation.evidence_refs if observation else [],
    )


def _item_from_bool(
    value: bool | None,
    *,
    default: ChecklistItemStatus | None = None,
) -> ChecklistItemStatus:
    if value is True:
        return ChecklistItemStatus.OBSERVED
    if value is False:
        return ChecklistItemStatus.NOT_OBSERVED
    return default or ChecklistItemStatus.NOT_CHECKED


def _access_barrier_status(
    observation: SourceVerificationObservation | None,
) -> ChecklistItemStatus:
    if observation is None or observation.access_barrier_observed is None:
        return ChecklistItemStatus.NOT_CHECKED
    if observation.access_barrier_observed:
        return ChecklistItemStatus.BLOCKED
    return ChecklistItemStatus.NOT_OBSERVED


def _checklist_status(
    public_entry_page: ChecklistItemStatus,
    query_behavior: ChecklistItemStatus,
    result_list: ChecklistItemStatus,
    detail_page: ChecklistItemStatus,
    access_barrier: ChecklistItemStatus,
) -> SourceVerificationChecklistStatus:
    if access_barrier == ChecklistItemStatus.BLOCKED:
        return SourceVerificationChecklistStatus.BLOCKED
    if detail_page == ChecklistItemStatus.OBSERVED:
        return SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED
    if query_behavior == ChecklistItemStatus.OBSERVED and result_list == ChecklistItemStatus.OBSERVED:
        return SourceVerificationChecklistStatus.QUERY_BEHAVIOR_OBSERVED
    if public_entry_page == ChecklistItemStatus.OBSERVED:
        return SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE
    if ChecklistItemStatus.FAILED in {
        public_entry_page,
        query_behavior,
        result_list,
        detail_page,
    }:
        return SourceVerificationChecklistStatus.FAILED
    return SourceVerificationChecklistStatus.NEEDS_MANUAL_REVIEW


def _next_action(status: SourceVerificationChecklistStatus) -> str:
    if status == SourceVerificationChecklistStatus.BLOCKED:
        return "review access boundary before any source update"
    if status == SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED:
        return "review source evidence for verified-candidate treatment"
    if status == SourceVerificationChecklistStatus.QUERY_BEHAVIOR_OBSERVED:
        return "manually inspect detail-page behavior"
    if status == SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE:
        return "manually inspect query, list, detail, captcha, and terms behavior"
    if status == SourceVerificationChecklistStatus.FAILED:
        return "repair or replace source target before source update"
    return "complete manual source verification checklist"


def _checklist_limitations(status: SourceVerificationChecklistStatus) -> list[str]:
    if status == SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE:
        return ["entry reachability is not query/list/detail verification"]
    if status in {
        SourceVerificationChecklistStatus.NEEDS_MANUAL_REVIEW,
        SourceVerificationChecklistStatus.NOT_CHECKED,
    }:
        return ["manual query/list/detail verification is incomplete"]
    if status == SourceVerificationChecklistStatus.QUERY_BEHAVIOR_OBSERVED:
        return ["detail-page behavior remains unverified"]
    return []


def _observation_reasons(
    observation: SourceVerificationObservation | None,
) -> list[str]:
    if observation is None:
        return ["no operator observation file was supplied"]
    return ["operator observation file supplied"]


def _observation_index(
    observations: Iterable[SourceVerificationObservation],
) -> dict[str, SourceVerificationObservation]:
    index: dict[str, SourceVerificationObservation] = {}
    for observation in observations:
        if observation.source_key:
            index[observation.source_key] = observation
        if observation.source_name:
            index[observation.source_name] = observation
    return index


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
