from constructionsight.intake_models import IntakeRouting
from constructionsight.intake_service import IntakeInspectionInput, inspect_lawful_input
from constructionsight.opportunity_models import OpportunityReadiness, OpportunityTransitionKind
from constructionsight.opportunity_service import build_opportunity_candidate


def test_build_opportunity_candidate_scores_transition_rich_intake_record() -> None:
    record = inspect_lawful_input(
        IntakeInspectionInput(
            content=b"""
            City of Hesperia filed SCH No. 2026061234 for warehouse construction.
            Project site: 123 Main Street. APN: 123-456-78.
            Permit No. BLD20260001 issued on 2026-06-01.
            CSLB: 123456. Estimated value: $3,000,000.
            Contact: planner@example.gov.
            """,
            source_name="manual transition note",
        )
    )

    candidate = build_opportunity_candidate(record)
    event_kinds = {event.event_kind for event in candidate.transition_events}

    assert candidate.lead_score == 100
    assert candidate.readiness == OpportunityReadiness.OUTREACH_READY
    assert OpportunityTransitionKind.CEQA_SIGNAL in event_kinds
    assert OpportunityTransitionKind.PERMIT_ISSUED in event_kinds
    assert OpportunityTransitionKind.CONTRACTOR_IDENTIFIED in event_kinds
    assert OpportunityTransitionKind.VALUATION_CHANGED in event_kinds
    assert OpportunityTransitionKind.SITE_ANCHOR in event_kinds
    assert OpportunityTransitionKind.CONTACT_CHANNEL in event_kinds
    assert candidate.site_hints["apn"] == "12345678"
    assert candidate.contact_hints["email"] == "planner@example.gov"


def test_permit_context_distinguishes_application_from_issued_signal() -> None:
    record = inspect_lawful_input(
        IntakeInspectionInput(
            content=b"Permit application received. Permit No. BLD20260001.",
            source_name="permit application note",
        )
    )

    candidate = build_opportunity_candidate(record)
    event_kinds = {event.event_kind for event in candidate.transition_events}

    assert OpportunityTransitionKind.PERMIT_APPLICATION in event_kinds
    assert OpportunityTransitionKind.PERMIT_ISSUED not in event_kinds


def test_non_opportunity_intake_keeps_limitations_visible() -> None:
    record = inspect_lawful_input(
        IntakeInspectionInput(content=b"\x00\x01\x02\x03", source_name="binary record")
    )
    assert record.routing == IntakeRouting.HUMAN_REVIEW

    candidate = build_opportunity_candidate(record)

    assert candidate.lead_score == 5
    assert candidate.readiness == OpportunityReadiness.NOT_QUALIFIED
    assert "no extracted material facts were available for opportunity scoring" in (
        candidate.limitations
    )
    assert any("unmapped evidence remains" in limitation for limitation in candidate.limitations)
