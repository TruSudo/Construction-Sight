from constructionsight.decision_record_models import (
    DecisionKind,
    DecisionMatchStatus,
    DecisionSourceKind,
)
from constructionsight.decision_record_service import (
    build_decision_record,
    match_decision_to_site,
    normalize_decision_title,
)


def test_normalize_decision_title_is_deterministic() -> None:
    assert normalize_decision_title("  Warehouse - CUP #1  ") == "WAREHOUSE CUP 1"


def test_build_decision_record_scores_site_and_source_signals() -> None:
    decision = build_decision_record(
        source_key="agenda:redlands",
        source_record_id="item-1",
        source_kind=DecisionSourceKind.PLANNING_COMMISSION,
        decision_kind=DecisionKind.ENTITLEMENT,
        title="Warehouse entitlement hearing",
        jurisdiction="Redlands",
        county="San Bernardino",
        case_number="CUP-1",
        site_key="site:abc",
        apn="123-456-78",
        applicant_name="Example Applicant",
        source_url="https://example.invalid/staff-report",
    )

    assert decision.decision_key.startswith("decision:")
    assert decision.normalized_title == "WAREHOUSE ENTITLEMENT HEARING"
    assert decision.apn == "12345678"
    assert decision.confidence_score == 100
    assert "decision includes a site key" in decision.reasons


def test_build_decision_record_preserves_missing_source_limitations() -> None:
    decision = build_decision_record(
        source_key="agenda:test",
        title="Project discussion",
    )

    assert decision.confidence_score == 20
    assert "decision source kind is unknown" in decision.limitations
    assert "decision has no site or APN hint" in decision.limitations
    assert "decision source URL is missing" in decision.limitations


def test_match_decision_to_site_returns_matched_for_site_key() -> None:
    decision = build_decision_record(
        source_key="agenda:test",
        title="Project approval",
        site_key="site:abc",
        apn="12345678",
    )

    match = match_decision_to_site(decision)

    assert match.status == DecisionMatchStatus.MATCHED
    assert match.site_key == "site:abc"
    assert match.confidence_score == 90


def test_match_decision_to_site_returns_review_needed_for_apn_only() -> None:
    decision = build_decision_record(
        source_key="agenda:test",
        title="Project approval",
        apn="123-456-78",
    )

    match = match_decision_to_site(decision)

    assert match.status == DecisionMatchStatus.REVIEW_NEEDED
    assert match.apn == "12345678"
    assert match.confidence_score == 20


def test_match_decision_to_site_returns_unmatched_without_site_hints() -> None:
    decision = build_decision_record(
        source_key="agenda:test",
        title="Project approval",
    )

    match = match_decision_to_site(decision)

    assert match.status == DecisionMatchStatus.UNMATCHED
    assert match.limitations == ["decision has no site key or APN hint"]
