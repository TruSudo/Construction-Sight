"""Contract checks for the five-case SMARTS enrichment research benchmark.

These tests validate fixture consistency. They DO NOT prove live record matching,
construction commencement, authorization, completeness, or data freshness.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

FIXTURE = (
    Path(__file__).parent
    / "fixtures/enrichment/smarts_five_project_pilot_2026_10_12.json"
)


@pytest.fixture(scope="module")
def pilot() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_five_unique_source_candidates_with_evidence(pilot: dict[str, object]) -> None:
    cases = pilot["cases"]
    assert isinstance(cases, list)
    assert len(cases) == 5
    assert len({entry["id"] for entry in cases}) == 5
    assert len({(entry["smarts"]["county"], entry["smarts"]["app_id"], entry["smarts"]["site_name"])
                for entry in cases}) == 5
    assert all(entry["link_status"] != "confirmed_verified" for entry in cases)
    assert all(entry["identity_checks"] and entry["next_evidence"] for entry in cases)


def test_each_claim_links_only_to_explicit_official_sources(pilot: dict[str, object]) -> None:
    approved_suffixes = (
        "ceqanet.lci.ca.gov",
        "cityofmenifee.us",
        "lake-elsinore.org",
        "palmdesert.gov",
        "citybigbearlake.com",
    )
    for case in pilot["cases"]:
        assert case["external_evidence"]
        for evidence in case["external_evidence"]:
            url = urlsplit(evidence["url"])
            assert url.scheme == "https"
            assert url.hostname is not None
            assert url.username is None and url.password is None
            assert any(
                url.hostname == suffix or url.hostname.endswith("." + suffix)
                for suffix in approved_suffixes
            )
            assert evidence["observations"]
            assert evidence["type"]


def test_regulatory_active_is_not_construction_activity(pilot: dict[str, object]) -> None:
    assert "not verified construction" in pilot["prohibited_inferences"][0].lower()
    assert "user-supplied" in pilot["smarts_observations_provenance"]
    for case in pilot["cases"]:
        assert case["smarts"]["regulatory_status"] == "Active"
        assert case["smarts"]["reported_commencement_date"]
        assert case["smarts"]["noi_processed_date"]


def test_hard_identity_edges_remain_unconfirmed(pilot: dict[str, object]) -> None:
    cases = {item["id"]: item for item in pilot["cases"]}
    assert cases["smarts_northern_gateway_menifee"]["candidate_relation"] == (
        "possible_offsite_infrastructure_of"
    )
    assert cases["smarts_o_resort_big_bear"]["smarts"]["app_id"] == "NA"
    assert cases["smarts_o_resort_big_bear"]["link_status"] == (
        "location_discrepancy_requires_resolution"
    )
    assert "2021 Corydon Gateway" in (
        cases["smarts_corydon_group_lake_elsinore"]["identity_checks"][0]
    )
    assert any(
        "withdrawn" in observation.lower()
        for item in cases["smarts_gateway_grand_terrace"]["external_evidence"]
        for observation in item["observations"]
    )
