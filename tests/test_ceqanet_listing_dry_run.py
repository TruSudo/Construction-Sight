from datetime import date

from constructionsight.adapters.ceqanet import CEQANET_SEARCH_URL
from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_dry_run import CeqanetListingDryRunExecutor
from constructionsight.legal import AccessDecision, AccessPolicyResult


def _allowed() -> AccessPolicyResult:
    return AccessPolicyResult(
        decision=AccessDecision.ALLOWED,
        reason="No known access restriction blocks lawful public collection.",
    )


def _blocked() -> AccessPolicyResult:
    return AccessPolicyResult(
        decision=AccessDecision.BLOCKED,
        reason="Robots policy disallows collection for the intended path.",
    )


def test_ceqanet_listing_dry_run_emits_request_intent_without_execution() -> None:
    query = CeqanetListingQuery(
        counties=("San Bernardino",),
        document_types=("EIR",),
        page_size=50,
        max_pages=2,
    )
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())

    report = CeqanetListingDryRunExecutor().run(plan)

    assert report.allowed is True
    assert report.planned_request_count == 2
    assert report.executed_request_count == 0
    assert report.maximum_records == 100
    assert report.downloads_documents is False
    assert report.mutates_remote_state is False
    assert report.requests[0].page_number == 1
    assert report.requests[0].method == "GET"
    assert report.requests[0].params == (
        ("DocumentType", "EIR - Draft EIR"),
        ("County", "San Bernardino"),
        ("page", "1"),
    )
    assert report.requests[0].url == (
        f"{CEQANET_SEARCH_URL}?"
        "DocumentType=EIR+-+Draft+EIR&County=San+Bernardino&page=1"
    )
    assert report.requests[1].url.startswith(f"{CEQANET_SEARCH_URL}?DocumentType=")
    assert report.requests[1].url.endswith("&page=2")


def test_ceqanet_listing_dry_run_blocks_requests_when_plan_is_blocked() -> None:
    query = CeqanetListingQuery(counties=("San Bernardino",), max_pages=2)
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _blocked())

    report = CeqanetListingDryRunExecutor().run(plan)

    assert report.allowed is False
    assert report.planned_request_count == 0
    assert report.executed_request_count == 0
    assert report.maximum_records == 0
    assert report.requests == ()
    assert "Robots policy disallows" in report.reason


def test_ceqanet_listing_dry_run_preserves_date_request_intent() -> None:
    query = CeqanetListingQuery(
        lead_agencies=("City of Fontana",),
        received_from=date(2026, 1, 1),
        received_to=date(2026, 1, 31),
    )
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())

    report = CeqanetListingDryRunExecutor().run(plan)

    assert report.requests[0].params == (
        ("StartRange", "2026-01-01"),
        ("EndRange", "2026-01-31"),
        ("LeadAgency", "City of Fontana"),
    )
    assert "StartRange=2026-01-01" in report.requests[0].url
    assert "EndRange=2026-01-31" in report.requests[0].url


def test_ceqanet_listing_dry_run_handles_existing_query_separator() -> None:
    query = CeqanetListingQuery(counties=("Riverside",))
    plan = CeqanetReadOnlyListingPlanner(
        search_url="https://example.test/search?mode=advanced"
    ).build_plan(query, _allowed())

    report = CeqanetListingDryRunExecutor().run(plan)

    assert report.requests[0].url == (
        "https://example.test/search?mode=advanced&County=Riverside"
    )
