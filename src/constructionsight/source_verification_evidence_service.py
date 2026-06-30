"""Source evidence package service."""

from __future__ import annotations

from urllib.parse import urlparse

from constructionsight.adapters.specs import AdapterFamilySpec, AdapterImplementationStatus
from constructionsight.models import PlatformFamily, PublicSource
from constructionsight.source_readiness_models import SourceReadinessRow, SourceReadinessStatus
from constructionsight.source_readiness_service import (
    HttpReachabilityChecker,
    build_source_readiness_report,
)
from constructionsight.source_verification_evidence_models import (
    PublicQueryEvidenceStatus,
    RedirectClassification,
    SourcePromotionRecommendation,
    SourceVerificationEvidencePackage,
    SourceVerificationEvidenceRow,
)


def build_source_verification_evidence_package(
    sources: list[PublicSource],
    adapter_specs: dict[PlatformFamily, AdapterFamilySpec],
    *,
    check_http: bool = False,
    http_checker: HttpReachabilityChecker | None = None,
) -> SourceVerificationEvidencePackage:
    """Build a report-only source evidence package."""

    readiness_report = build_source_readiness_report(
        sources,
        adapter_specs,
        check_http=check_http,
        http_checker=http_checker,
    )
    return SourceVerificationEvidencePackage.from_rows(
        [_evidence_row(row) for row in readiness_report.rows]
    )


def _evidence_row(row: SourceReadinessRow) -> SourceVerificationEvidenceRow:
    recommendation = _recommendation(row)
    redirect_classification = _redirect_classification(
        row.public_url,
        row.http_reachability.final_url,
        row.http_reachability.checked,
    )
    return SourceVerificationEvidenceRow(
        source_key=row.source_key,
        source_name=row.source_name,
        platform_family=row.platform_family,
        original_url=row.public_url,
        final_url=row.http_reachability.final_url,
        http_status_code=row.http_reachability.status_code,
        http_checked=row.http_reachability.checked,
        redirect_classification=redirect_classification,
        verification_status=row.verification_status,
        adapter_status=row.adapter_status,
        readiness_status=row.readiness_status.value,
        lawful_access_boundary=row.lawful_access_boundary,
        public_query_evidence_status=_public_query_evidence_status(row.adapter_status),
        operator_review_required=True,
        recommendation=recommendation,
        reasons=_unique(
            [
                row.reason,
                f"readiness status is {row.readiness_status.value}",
                f"adapter status is {row.adapter_status}",
                f"source verification status is {row.verification_status}",
            ]
        ),
        limitations=_unique(
            [
                *row.limitations,
                *_redirect_limitations(redirect_classification),
                *_adapter_limitations(row.adapter_status),
            ]
        ),
        next_action=_next_action(row, recommendation),
    )


def _recommendation(row: SourceReadinessRow) -> SourcePromotionRecommendation:
    if row.readiness_status == SourceReadinessStatus.SEED_ONLY:
        return SourcePromotionRecommendation.KEEP_SEED_ONLY
    if row.readiness_status == SourceReadinessStatus.REACHABLE:
        return SourcePromotionRecommendation.KEEP_UNVERIFIED_REACHABLE
    if row.readiness_status == SourceReadinessStatus.BLOCKED:
        return SourcePromotionRecommendation.MARK_BLOCKED_CANDIDATE
    if row.readiness_status == SourceReadinessStatus.FAILED:
        return SourcePromotionRecommendation.MARK_FAILED_CANDIDATE
    if row.readiness_status == SourceReadinessStatus.PARTIAL:
        return SourcePromotionRecommendation.MARK_PARTIAL_CANDIDATE
    return SourcePromotionRecommendation.VERIFIED_CANDIDATE_REVIEW


def _redirect_classification(
    original_url: str,
    final_url: str | None,
    http_checked: bool,
) -> RedirectClassification:
    if not http_checked:
        return RedirectClassification.NOT_CHECKED
    if final_url is None:
        return RedirectClassification.UNKNOWN
    original = urlparse(original_url)
    final = urlparse(final_url)
    if original.geturl() == final.geturl():
        return RedirectClassification.NO_REDIRECT
    if original.scheme == "https" and final.scheme == "http":
        return RedirectClassification.DOWNGRADED_TO_HTTP
    if original.netloc == final.netloc:
        return RedirectClassification.SAME_HOST_REDIRECT
    return RedirectClassification.CROSS_HOST_REDIRECT


def _public_query_evidence_status(adapter_status: str) -> PublicQueryEvidenceStatus:
    if adapter_status == AdapterImplementationStatus.PLACEHOLDER.value:
        return PublicQueryEvidenceStatus.PLACEHOLDER_ADAPTER
    if adapter_status == AdapterImplementationStatus.CONTRACT_READY.value:
        return PublicQueryEvidenceStatus.ADAPTER_CONTRACT_READY
    return PublicQueryEvidenceStatus.UNKNOWN_NEEDS_MANUAL_REVIEW


def _redirect_limitations(
    redirect_classification: RedirectClassification,
) -> list[str]:
    if redirect_classification == RedirectClassification.CROSS_HOST_REDIRECT:
        return ["source redirects to a different host"]
    if redirect_classification == RedirectClassification.DOWNGRADED_TO_HTTP:
        return ["source redirects from HTTPS to HTTP"]
    if redirect_classification == RedirectClassification.UNKNOWN:
        return ["redirect behavior could not be classified"]
    if redirect_classification == RedirectClassification.NOT_CHECKED:
        return ["redirect behavior was not checked"]
    return []


def _adapter_limitations(adapter_status: str) -> list[str]:
    if adapter_status == AdapterImplementationStatus.PLACEHOLDER.value:
        return ["adapter is placeholder-only"]
    if adapter_status == AdapterImplementationStatus.CONTRACT_READY.value:
        return ["adapter contract is not live source coverage"]
    return []


def _next_action(
    row: SourceReadinessRow,
    recommendation: SourcePromotionRecommendation,
) -> str:
    if recommendation == SourcePromotionRecommendation.KEEP_SEED_ONLY:
        return "run source readiness with HTTP checking before source review"
    if recommendation == SourcePromotionRecommendation.KEEP_UNVERIFIED_REACHABLE:
        return "perform manual query/list/detail review"
    if recommendation == SourcePromotionRecommendation.MARK_BLOCKED_CANDIDATE:
        return "review lawful access boundary"
    if recommendation == SourcePromotionRecommendation.MARK_FAILED_CANDIDATE:
        return "repair source URL or mark failed after review"
    if recommendation == SourcePromotionRecommendation.MARK_PARTIAL_CANDIDATE:
        return "complete missing source or adapter evidence"
    return row.next_action


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
