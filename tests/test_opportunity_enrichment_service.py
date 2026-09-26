from constructionsight.contractor_identity_service import build_contractor_identity
from constructionsight.decision_record_models import DecisionKind, DecisionSourceKind
from constructionsight.decision_record_service import build_decision_record
from constructionsight.domain_types import confidence_band
from constructionsight.opportunity_enrichment_models import EnrichmentSignalKind
from constructionsight.opportunity_enrichment_service import enrich_opportunity
from constructionsight.opportunity_scoring_profile import OpportunityScoringProfile
from constructionsight.permit_transition_models import PermitTransition, PermitTransitionKind
from constructionsight.site_resolution_models import (
    SiteResolutionCandidate,
    SiteResolutionResult,
    SiteResolutionStatus,
)


def _site_result() -> SiteResolutionResult:
    return SiteResolutionResult(
        source_name="test source",
        status=SiteResolutionStatus.RESOLVED,
        primary_site_key="site:test",
        candidates=[
            SiteResolutionCandidate(
                site_key="site:test",
                match_strength="exact",
                confidence_score=90,
                confidence_band=confidence_band(90),
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


def _custom_profile() -> OpportunityScoringProfile:
    return OpportunityScoringProfile(
        profile_key="opportunity-scoring:custom",
        version="1",
        site_resolved_score=30,
        site_partial_score=12,
        permit_transition_scores={kind: 1 for kind in PermitTransitionKind},
        contractor_with_license_score=2,
        contractor_without_license_score=1,
        decision_with_site_score=3,
        decision_without_site_score=2,
        high_value_threshold=30,
        review_threshold=20,
        monitor_threshold=1,
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

    assert report.lead_score == 60
    assert report.scoring_profile_key == "opportunity-scoring:default"
    assert report.scoring_profile_version == "2026-09-25.1"
    assert EnrichmentSignalKind.PARCEL_SITE in signal_kinds
    assert EnrichmentSignalKind.PERMIT_TRANSITION in signal_kinds
    assert EnrichmentSignalKind.CONTRACTOR_IDENTITY in signal_kinds
    assert EnrichmentSignalKind.DECISION_SIGNAL in signal_kinds
    assert report.next_action == "review limitations before outreach"


def test_enrich_opportunity_accepts_custom_scoring_profile() -> None:
    contractor = build_contractor_identity(
        display_name="Acme Builders",
        license_number="123456",
    )

    report = enrich_opportunity(
        base_candidate_id="candidate:test",
        site_resolution=_site_result(),
        permit_transitions=[_permit_transition()],
        contractor_identity=contractor,
        scoring_profile=_custom_profile(),
    )

    assert report.lead_score == 30
    assert report.scoring_profile_key == "opportunity-scoring:custom"
    assert report.scoring_profile_version == "1"
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

    assert report.lead_score == 3
    assert "no contractor license signal was available" in report.limitations
    assert report.next_action == "monitor and enrich with more source evidence"


def test_high_nominal_signal_cannot_become_actionable_with_low_confidence() -> None:
    candidate = SiteResolutionCandidate(
        site_key="site:low-confidence",
        match_strength="moderate",
        confidence_score=50,
        confidence_band=confidence_band(50),
        reasons=["synthetic low-confidence site anchor"],
    )
    site = SiteResolutionResult(
        source_name="test source",
        status=SiteResolutionStatus.RESOLVED,
        primary_site_key=candidate.site_key,
        candidates=[candidate],
    )
    profile = OpportunityScoringProfile(
        profile_key="opportunity-scoring:confidence-gate",
        version="1",
        site_resolved_score=100,
        site_partial_score=50,
        permit_transition_scores={kind: 0 for kind in PermitTransitionKind},
        contractor_with_license_score=0,
        contractor_without_license_score=0,
        decision_with_site_score=0,
        decision_without_site_score=0,
        high_value_threshold=50,
        review_threshold=50,
        monitor_threshold=1,
        minimum_actionable_confidence=70,
    )

    report = enrich_opportunity(
        base_candidate_id="candidate:low-confidence",
        site_resolution=site,
        scoring_profile=profile,
    )

    assert report.signals[0].score_delta == 100
    assert report.signals[0].operational_score_delta == 50
    assert report.lead_score == 50
    assert report.confidence_score == 50
    assert report.next_action == "review limitations before outreach"


def test_zero_confidence_signal_contributes_no_operational_score() -> None:
    candidate = SiteResolutionCandidate(
        site_key="site:zero-confidence",
        match_strength="weak",
        confidence_score=0,
        confidence_band=confidence_band(0),
        reasons=["synthetic zero-confidence site signal"],
    )
    site = SiteResolutionResult(
        source_name="test source",
        status=SiteResolutionStatus.RESOLVED,
        primary_site_key=candidate.site_key,
        candidates=[candidate],
    )

    report = enrich_opportunity(
        base_candidate_id="candidate:zero-confidence",
        site_resolution=site,
    )

    assert report.signals[0].score_delta == 20
    assert report.signals[0].operational_score_delta == 0
    assert report.lead_score == 0
    assert report.next_action == (
        "hold until parcel, permit, contractor, or decision signal appears"
    )
