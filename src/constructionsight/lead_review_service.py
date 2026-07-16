"""Lead review package service."""

from __future__ import annotations

import hashlib

from constructionsight.lead_review_models import (
    LeadReviewItem,
    LeadReviewPackage,
    LeadReviewStatus,
)
from constructionsight.opportunity_enrichment_models import OpportunityEnrichmentReport


def build_lead_review_package(report: OpportunityEnrichmentReport) -> LeadReviewPackage:
    """Build a reviewable lead package from an enrichment report."""

    status = _status_for_report(report)
    items = _items_for_report(report, status)
    summary = _summary_for_report(report, status)
    return LeadReviewPackage(
        package_id=_package_id(report),
        base_candidate_id=report.base_candidate_id,
        lead_score=report.lead_score,
        status=status,
        summary=summary,
        items=items,
        evidence_notes=_evidence_notes(report),
        limitations=list(report.limitations),
        review_note=_review_note(status, report.limitations),
    )


def _status_for_report(report: OpportunityEnrichmentReport) -> LeadReviewStatus:
    """Return review status from enrichment score and limitations."""

    if report.lead_score == 0:
        return LeadReviewStatus.HOLD
    if report.lead_score < 50:
        return LeadReviewStatus.MONITOR
    if report.limitations:
        return LeadReviewStatus.REVIEW_REQUIRED
    return LeadReviewStatus.READY


def _items_for_report(
    report: OpportunityEnrichmentReport,
    status: LeadReviewStatus,
) -> list[LeadReviewItem]:
    """Build next-step items for a review package."""

    if status == LeadReviewStatus.HOLD:
        return []
    blocked = status == LeadReviewStatus.REVIEW_REQUIRED
    return [
        LeadReviewItem(
            item_key=f"lead-item:{_short_hash(report.report_id)}",
            label=_label_for_status(status),
            rationale=report.next_action,
            blocked_by_limitations=blocked,
        )
    ]


def _label_for_status(status: LeadReviewStatus) -> str:
    """Return label for a review status."""

    if status == LeadReviewStatus.READY:
        return "prepare reviewed lead package"
    if status == LeadReviewStatus.REVIEW_REQUIRED:
        return "review source limitations"
    if status == LeadReviewStatus.MONITOR:
        return "monitor for stronger signals"
    return "hold"


def _summary_for_report(
    report: OpportunityEnrichmentReport,
    status: LeadReviewStatus,
) -> str:
    """Build deterministic lead summary."""

    return (
        f"Lead score {report.lead_score}; status {status.value}; "
        f"signals {len(report.signals)}."
    )


def _evidence_notes(report: OpportunityEnrichmentReport) -> list[str]:
    """Return review evidence notes from enrichment signals."""

    return [f"{signal.signal_kind.value}: {signal.reason}" for signal in report.signals]


def _review_note(status: LeadReviewStatus, limitations: list[str]) -> str | None:
    """Return review note when needed."""

    if status == LeadReviewStatus.REVIEW_REQUIRED:
        return f"Resolve {len(limitations)} limitation(s) before review completion."
    if status == LeadReviewStatus.HOLD:
        return "No source signal is strong enough for review."
    return None


def _package_id(report: OpportunityEnrichmentReport) -> str:
    """Build deterministic lead review package id."""

    return f"lead-review:{_short_hash(report.report_id)}"


def _short_hash(value: str) -> str:
    """Return a short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
