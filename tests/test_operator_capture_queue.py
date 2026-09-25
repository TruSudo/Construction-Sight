"""Fail-closed tests for the retained exact-SCH operator review queue."""

from __future__ import annotations

import json
from copy import deepcopy

import pytest

from constructionsight.operator_capture_queue import load_operator_capture_queue


def _payload() -> dict[str, object]:
    return {
        "schema_version": "ceqanet_exact_sch_capture_queue.v1",
        "listing_artifact_sha256": "b" * 64,
        "listing_plan_id": "fixture-plan",
        "listing_pages_reviewed": 2,
        "listing_records_parsed": 5,
        "candidate_count": 1,
        "excluded_observations": {
            "missing_or_ambiguous_sch": 1,
            "outside_target_counties": 3,
        },
        "candidates": [
            {
                "sch_number": "2026012345",
                "source_claimed_county": "Riverside",
                "source_claimed_title": "Synthetic source claim",
                "title_requires_detail_enrichment": True,
                "official_detail_url": "https://ceqanet.lci.ca.gov/Project/2026012345",
                "observation_pages": [1, 2],
                "source_observation_count": 2,
                "review_state": "unverified_source_claim",
                "candidate_only": True,
                "network_executed_for_candidate": False,
                "persistence_mutated": False,
            }
        ],
        "network_executed": False,
        "persistence_mutated": False,
        "commercial_leads_created": False,
        "limitations": ["Fixture only."],
    }


def _write(tmp_path, payload: object):
    path = tmp_path / "queue.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_operator_queue_reduces_retained_artifact_to_read_only_presentation(tmp_path):
    result = load_operator_capture_queue(_write(tmp_path, _payload()))

    assert result["schema_version"] == "constructionsight.operator_capture_queue.v1"
    assert result["configured"] is True
    assert result["candidate_count"] == 1
    assert result["network_executed"] is False
    assert result["persistence_mutated"] is False
    assert result["commercial_leads_created"] is False
    assert result["candidates"][0]["sch_number"] == "2026012345"
    assert "Fixture only." not in result["limitations"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(candidate_count=2), "candidate count"),
        (lambda value: value.update(network_executed=True), "authority state"),
        (
            lambda value: value["candidates"][0].update(
                source_claimed_county="Orange"
            ),
            "target scope",
        ),
        (
            lambda value: value["candidates"][0].update(
                sch_number="2026012346"
            ),
            "exact official SCH page",
        ),
        (
            lambda value: value["candidates"][0].update(
                candidate_only=False
            ),
            "authority state",
        ),
    ],
)
def test_operator_queue_rejects_inconsistent_identity_scope_and_authority(
    tmp_path, mutation, message
):
    payload = deepcopy(_payload())
    mutation(payload)

    with pytest.raises(ValueError, match=message):
        load_operator_capture_queue(_write(tmp_path, payload))


def test_operator_queue_rejects_duplicate_or_noncanonical_sch_order(tmp_path):
    payload = _payload()
    candidate = deepcopy(payload["candidates"][0])
    payload["candidates"] = [candidate, deepcopy(candidate)]
    payload["candidate_count"] = 2

    with pytest.raises(ValueError, match="duplicated or not canonically ordered"):
        load_operator_capture_queue(_write(tmp_path, payload))
