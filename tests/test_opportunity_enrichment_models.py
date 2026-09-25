import pytest
from pydantic import ValidationError

from constructionsight.domain_types import confidence_band
from constructionsight.opportunity_enrichment_models import (
    EnrichmentSignalKind,
    OpportunityEnrichmentReport,
    OpportunityEnrichmentSignal,
)


def test_enrichment_signal_rejects_duplicate_limitations() -> None:
    with pytest.raises(ValidationError):
        OpportunityEnrichmentSignal(
            signal_key="signal:test",
            signal_kind=EnrichmentSignalKind.PARCEL_SITE,
            label="site",
            score_delta=10,
            reason="test",
            limitations=["x", "x"],
        )


def test_enrichment_report_requires_matching_confidence_band() -> None:
    signal = OpportunityEnrichmentSignal(
        signal_key="signal:test",
        signal_kind=EnrichmentSignalKind.PARCEL_SITE,
        label="site",
        score_delta=10,
        confidence_score=80,
        reason="test",
    )

    with pytest.raises(ValidationError):
        OpportunityEnrichmentReport(
            report_id="opportunity-enrichment:test",
            base_candidate_id="candidate:test",
            lead_score=10,
            confidence_score=80,
            confidence_band=confidence_band(10),
            signals=[signal],
            next_action="test",
        )


def test_enrichment_report_requires_signals_for_positive_score() -> None:
    with pytest.raises(ValidationError):
        OpportunityEnrichmentReport(
            report_id="opportunity-enrichment:test",
            base_candidate_id="candidate:test",
            lead_score=10,
            confidence_score=0,
            confidence_band=confidence_band(0),
            next_action="test",
        )


def test_enrichment_report_serializes() -> None:
    signal = OpportunityEnrichmentSignal(
        signal_key="signal:test",
        signal_kind=EnrichmentSignalKind.PERMIT_TRANSITION,
        label="status_changed",
        score_delta=20,
        confidence_score=80,
        reason="status changed",
    )
    report = OpportunityEnrichmentReport(
        report_id="opportunity-enrichment:test",
        base_candidate_id="candidate:test",
        lead_score=16,
        confidence_score=80,
        confidence_band=confidence_band(80),
        signals=[signal],
        next_action="review",
    )

    assert signal.operational_score_delta == 16
    assert report.to_dict()["lead_score"] == 16


def test_enrichment_report_rejects_unweighted_caller_score() -> None:
    signal = OpportunityEnrichmentSignal(
        signal_key="signal:weighted",
        signal_kind=EnrichmentSignalKind.PERMIT_TRANSITION,
        label="status_changed",
        score_delta=20,
        confidence_score=50,
        reason="status changed",
    )

    with pytest.raises(
        ValidationError,
        match="lead_score must use confidence-weighted signal contributions",
    ):
        OpportunityEnrichmentReport(
            report_id="opportunity-enrichment:forged-score",
            base_candidate_id="candidate:test",
            lead_score=20,
            confidence_score=50,
            confidence_band=confidence_band(50),
            signals=[signal],
            next_action="prepare outreach preview",
        )


def test_enrichment_report_rejects_caller_supplied_confidence() -> None:
    signal = OpportunityEnrichmentSignal(
        signal_key="signal:confidence",
        signal_kind=EnrichmentSignalKind.PERMIT_TRANSITION,
        label="status_changed",
        score_delta=20,
        confidence_score=40,
        reason="status changed",
    )

    with pytest.raises(
        ValidationError,
        match="confidence_score must be derived from enrichment signals",
    ):
        OpportunityEnrichmentReport(
            report_id="opportunity-enrichment:forged-confidence",
            base_candidate_id="candidate:test",
            lead_score=8,
            confidence_score=90,
            confidence_band=confidence_band(90),
            signals=[signal],
            next_action="review",
        )
