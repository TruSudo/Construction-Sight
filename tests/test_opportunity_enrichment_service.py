from constructionsight.contractor_identity_service import build_contractor_identity
from constructionsight.decision_record_models import DecisionKind, DecisionSourceKind
from constructionsight.decision_record_service import build_decision_record
from constructionsight.opportunity_enrichment_models import EnrichmentSignalKind
from constructionsight.opportunity_enrichment_service import enrich_opportunity
from constructionsight.permit_transition_models import PermitTransition, PermitTransitionKind
from constructionsight.site_resolution_models import (
    SiteResolutionCandidate,
    SiteResolutionResult,
    SiteResolutionStatus,
)


def _site_result() -> SiteResolutionResult:
    return SiteResolutionResult(
        resolution_id="site-resolution:test",
        source_name="test source",
        status=SiteResolutionStatus.RESOLVED,
        primary_site_key="site:test",
        candidates=[
            SiteResolutionCandidate(
                site_key="site:test",
                confidence_score=90,
                confidence_band="high",
                reasons=["site matched"],
            )
        ],
    )


def _permit_transition() -> PermitTransition:
    return PermitTransition(
        transition_id="permit-transition:test",
        transition_kind=PermitTransitionKind.STATUS_CHANGED,
        source_key="permit:test",
        source_record_id="permit:1",
        field_name="status",
        previous_value="applied",
        current_value="issued",
        reason="status changed",
    )


def test_enrich_opportunity_combines_all_signal_layers() -> None:
    contractor = build_contractor_identity(
        display_name="Acme Builders",
        license_number="123456",
    )
    decision = build_decision_record(
        source_key="decision:test",
        title="Project approval",
        source_kind=DecisionSourceKind.AGENDA,
        decision_kind=DecisionKind.APPROVAL,
        site_key="site:test",
        source_url="https://example.invalid/item",
    )

    report = enrich_opportunity(
        base_candidate_id="candidate:test",
        site_resolution=_site_result(),
        permit_transitions=[_permit_transition()],
        contractor_identity=contractor,
        decision_records=[decision],
    )
    signal_kinds = {signal.signal_kind for signal in report.signals}

    assert report.lead_score == 70
    assert EnrichmentSignalKind.PARCEL_SITE in signal_kinds
    assert EnrichmentSignalKind.PERMIT_TRANSITION in signal_kinds
    assert EnrichmentSignalKind.CONTRACTOR_IDENTITY in signal_kinds
    assert EnrichmentSignalKind.DECISION_SIGNAL in signal_kinds
    assert report.next_action == "prepare outreach preview"


def test_enrich_opportunity_handles_no_signals() -> None:
    report = enrich_opportunity(base_candidate_id="candidate:test")

    assert report.lead_score == 0
    assert report.confidence_score == 0
    assert report.signals == []
    assert report.limitations == ["no enrichment signals were available"]
    assert report.next_action == (
        "hold until parcel, permit, contractor, or decision signal appears"
    )


def test_enrich_opportunity_keeps_limitations_for_lower_confidence_signals() -> None:
    contractor = build_contractor_identity(display_name="Acme Builders")

    report = enrich_opportunity(
        base_candidate_id="candidate:test",
        contractor_identity=contractor,
    )

    assert report.lead_score == 8
    assert "no contractor license signal was available" in report.limitations
    assert report.next_action == "monitor and enrich with more source evidence"
