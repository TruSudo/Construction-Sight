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
        lead_score=20,
        confidence_score=80,
        confidence_band=confidence_band(80),
        signals=[signal],
        next_action="review",
    )

    assert report.to_dict()["lead_score"] == 20
