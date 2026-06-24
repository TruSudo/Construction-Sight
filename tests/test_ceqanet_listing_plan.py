from datetime import date

import pytest

from constructionsight.adapters.ceqanet import CEQANET_SEARCH_URL
from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
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


def test_ceqanet_listing_query_requires_a_bounding_filter() -> None:
    with pytest.raises(ValueError, match="requires at least one bounding query filter"):
        CeqanetListingQuery()


def test_ceqanet_listing_query_rejects_unbounded_page_size() -> None:
    with pytest.raises(ValueError, match="page_size must be between 1 and 100"):
        CeqanetListingQuery(counties=("San Bernardino",), page_size=101)


def test_ceqanet_listing_query_rejects_unbounded_max_pages() -> None:
    with pytest.raises(ValueError, match="max_pages must be between 1 and 10"):
        CeqanetListingQuery(counties=("San Bernardino",), max_pages=11)


def test_ceqanet_listing_query_rejects_reversed_date_ranges() -> None:
    with pytest.raises(ValueError, match="received_from must be on or before received_to"):
        CeqanetListingQuery(
            counties=("San Bernardino",),
            received_from=date(2026, 2, 1),
            received_to=date(2026, 1, 1),
        )


def test_ceqanet_listing_planner_builds_get_only_pages_after_access_allowance() -> None:
    query = CeqanetListingQuery(
        counties=("San Bernardino",),
        document_types=("EIR",),
        text_terms=("warehouse",),
        high_signal_only=True,
        page_size=50,
        max_pages=2,
    )

    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())

    assert plan.allowed is True
    assert plan.maximum_records == 100
    assert len(plan.pages) == 2
    assert {page.method for page in plan.pages} == {"GET"}
    assert {page.search_url for page in plan.pages} == {CEQANET_SEARCH_URL}
    assert all(page.downloads_documents is False for page in plan.pages)
    assert all(page.mutates_remote_state is False for page in plan.pages)
    assert plan.pages[0].params == (
        ("DocumentType", "EIR - Draft EIR"),
        ("County", "San Bernardino"),
        ("page", "1"),
    )
    assert plan.pages[1].params[-1] == ("page", "2")


def test_ceqanet_listing_planner_blocks_pages_when_access_preflight_blocks() -> None:
    query = CeqanetListingQuery(counties=("San Bernardino",), page_size=25, max_pages=2)

    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _blocked())

    assert plan.allowed is False
    assert plan.pages == ()
    assert plan.maximum_records == 0
    assert "Robots policy disallows" in plan.reason


def test_ceqanet_listing_planner_includes_date_filters_deterministically() -> None:
    query = CeqanetListingQuery(
        lead_agencies=("City of Fontana",),
        received_from=date(2026, 1, 1),
        received_to=date(2026, 1, 31),
        posted_from=date(2026, 2, 1),
        posted_to=date(2026, 2, 28),
    )

    plan = CeqanetReadOnlyListingPlanner().build_plan(query, _allowed())

    assert plan.pages[0].params == (
        ("StartRange", "2026-01-01"),
        ("EndRange", "2026-01-31"),
        ("LeadAgency", "City of Fontana"),
        ("StateReviewPeriodEnd", "2026-02-01"),
        ("PublicReviewPeriodEnd", "2026-02-28"),
    )
