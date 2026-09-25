from constructionsight.domain_types import confidence_band
from constructionsight.lead_review_models import LeadReviewStatus
from constructionsight.lead_review_service import build_lead_review_package
from constructionsight.opportunity_enrichment_models import (
    EnrichmentSignalKind,
    OpportunityEnrichmentReport,
    OpportunityEnrichmentSignal,
)


def _signal(score_delta: int = 80, limitation: str | None = None) -> OpportunityEnrichmentSignal:
    limitations = [limitation] if limitation else []
    return OpportunityEnrichmentSignal(
        signal_key="signal:test",
        signal_kind=EnrichmentSignalKind.PERMIT_TRANSITION,
        label="permit",
        score_delta=score_delta,
        confidence_score=80,
        reason="permit status changed",
        limitations=limitations,
    )


def _report(
    *,
    lead_score: int,
    signals: list[OpportunityEnrichmentSignal],
    limitations: list[str] | None = None,
) -> OpportunityEnrichmentReport:
    confidence_score = 80 if signals else 0
    return OpportunityEnrichmentReport(
        report_id="opportunity-enrichment:test",
        base_candidate_id="candidate:test",
        lead_score=lead_score,
        confidence_score=confidence_score,
        confidence_band=confidence_band(confidence_score),
        signals=signals,
        limitations=limitations or [],
        next_action="test next step",
    )


def test_build_lead_review_package_ready() -> None:
    package = build_lead_review_package(
        _report(lead_score=80, signals=[_signal(score_delta=100)])
    )

    assert package.status == LeadReviewStatus.READY
    assert package.items
    assert package.limitations == []
    assert package.review_note is None


def test_build_lead_review_package_review_required() -> None:
    package = build_lead_review_package(
        _report(
            lead_score=80,
            signals=[_signal(score_delta=100, limitation="source needs review")],
            limitations=["source needs review"],
        )
    )

    assert package.status == LeadReviewStatus.REVIEW_REQUIRED
    assert package.items[0].blocked_by_limitations is True
    assert package.review_note == "Resolve 1 limitation(s) before review completion."


def test_build_lead_review_package_monitor() -> None:
    package = build_lead_review_package(
        _report(lead_score=20, signals=[_signal(score_delta=25)])
    )

    assert package.status == LeadReviewStatus.MONITOR
    assert package.items[0].label == "monitor for stronger signals"


def test_build_lead_review_package_hold() -> None:
    package = build_lead_review_package(_report(lead_score=0, signals=[]))

    assert package.status == LeadReviewStatus.HOLD
    assert package.items == []
    assert package.review_note == "No source signal is strong enough for review."


def test_build_lead_review_package_preserves_evidence_notes() -> None:
    package = build_lead_review_package(
        _report(lead_score=80, signals=[_signal(score_delta=100)])
    )

    assert package.evidence_notes == ["permit_transition: permit status changed"]
