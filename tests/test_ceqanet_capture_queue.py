"""Offline retained-listing discovery into guarded manual CEQAnet SCH capture candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from constructionsight.ceqanet_capture_queue import build_reviewed_ceqanet_capture_queue
from constructionsight.ceqanet_csv_operator_bridge_cli import app

runner = CliRunner()


def _card(
    sch: str, *, county: str = "Riverside", link_sch: str | None = None,
    title: str = "Source-claimed project title",
) -> str:
    link = link_sch or sch
    return (
        '<div class="search-result">'
        f'<a href="/Project/{link}">{title}</a>'
        f'<span>SCH Number</span><span>{sch}</span>'
        f'<span>County</span><span>{county}</span>'
        "</div>"
    )


def _listing(*pages: str) -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_listing_execution.v2",
            "allowed": True,
            "planned_request_count": len(pages),
            "executed_request_count": len(pages),
            "successful_response_count": len(pages),
            "failed_response_count": 0,
            "plan_id": "bounded-test-listing-plan",
            "access": {"decision": "allowed"},
            "authorization": {"decision_id": "synthetic-authorization-id"},
        },
        "snapshots": [
            {
                "page_number": i,
                "method": "GET",
                "request_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
                "final_url": "https://ceqanet.lci.ca.gov/Search?County=Riverside",
                "status_code": 200,
                "content_type": "text/html; charset=utf-8",
                "body_text": html,
                "body_length": len(html),
                "body_truncated": False,
                "executed": True,
                "reachable": True,
                "error": None,
                "failure_kind": "none",
            }
            for i, html in enumerate(pages, 1)
        ],
    }


def _derive(payload: dict[str, object]) -> dict[str, object]:
    raw = json.dumps(payload, sort_keys=True).encode()
    return build_reviewed_ceqanet_capture_queue(payload, original_bytes=raw)


def test_reviewed_listing_queue_deduplicates_only_exact_sch_and_counts_observations() -> None:
    payload = _listing(
        _card("2026030377") + _card("2026061234", county="San Bernardino"),
        _card("2026030377", title="Alternate source-claimed document title"),
    )
    queue = _derive(payload)
    assert queue["schema_version"] == "ceqanet_exact_sch_capture_queue.v1"
    assert queue["listing_pages_reviewed"] == 2
    assert queue["listing_records_parsed"] == 3
    assert queue["candidate_count"] == 2
    assert queue["network_executed"] is False
    assert queue["persistence_mutated"] is False
    assert queue["commercial_leads_created"] is False
    assert queue["excluded_observations"] == {
        "missing_or_ambiguous_sch": 0, "outside_target_counties": 0,
    }
    cabazon, fontana = queue["candidates"]
    assert cabazon["sch_number"] == "2026030377"
    assert cabazon["source_claimed_county"] == "Riverside"
    assert cabazon["source_observation_count"] == 2
    assert cabazon["observation_pages"] == [1, 2]
    assert cabazon["official_detail_url"] == "https://ceqanet.lci.ca.gov/Project/2026030377"
    assert cabazon["review_state"] == "unverified_source_claim"
    assert cabazon["candidate_only"] is True
    assert fontana["sch_number"] == "2026061234"
    assert fontana["source_claimed_county"] == "San Bernardino"
    assert fontana["source_observation_count"] == 1


@pytest.mark.parametrize(
    "field,changed",
    [
        ("body_truncated", True),
        ("status_code", 503),
        ("reachable", False),
        ("executed", False),
        ("error", "network-error"),
        ("failure_kind", "oversized_response"),
        ("method", "POST"),
        ("final_url", "https://ceqanet.lci.ca.gov/Project/2026030377"),
        ("request_url", "https://example.org/Search"),
        ("content_type", "application/json"),
        ("body_text", ""),
        ("page_number", 2),
    ],
)
def test_queue_refuses_incomplete_unsafe_or_mislabeled_listing_page(
    field: str, changed: object,
) -> None:
    listing = _listing(_card("2026030377"))
    listing["snapshots"][0][field] = changed
    with pytest.raises(ValueError):
        _derive(listing)


@pytest.mark.parametrize(
    "field,changed",
    [
        ("allowed", False),
        ("executed_request_count", 0),
        ("successful_response_count", 0),
        ("failed_response_count", 1),
        ("planned_request_count", 2),
        ("schema_version", "ceqanet_listing_execution.v1"),
        ("authorization", {}),
        ("access", {"decision": "blocked"}),
    ],
)
def test_queue_requires_complete_authorized_v2_metadata(field: str, changed: object) -> None:
    listing = _listing(_card("2026030377"))
    listing["metadata"][field] = changed
    with pytest.raises(ValueError):
        _derive(listing)


def test_queue_excludes_unknown_county_and_mismatched_sch_without_guessing() -> None:
    listing = _listing(
        _card("2026030377")
        + _card("2026030378", county="Unknown")
        + _card("2026030379", link_sch="2026030380")
        + _card("2026030381", county="Los Angeles")
    )
    queue = _derive(listing)
    assert queue["candidate_count"] == 1
    assert queue["excluded_observations"] == {
        "missing_or_ambiguous_sch": 1, "outside_target_counties": 2,
    }


def test_queue_rejects_cross_page_county_conflict_for_same_sch() -> None:
    listing = _listing(
        _card("2026030377", county="Riverside"),
        _card("2026030377", county="San Bernardino"),
    )
    with pytest.raises(ValueError, match="conflicting county claims"):
        _derive(listing)


def test_queue_rejects_excess_pages_and_does_not_silently_truncate() -> None:
    listing = _listing(*(_card("2026030377") for _ in range(11)))
    with pytest.raises(ValueError, match="complete authorized page set"):
        _derive(listing)


def test_discover_preview_cli_retains_exact_listing_digest_without_network_or_sqlite(
    tmp_path: Path,
) -> None:
    listing_path = tmp_path / "existing-listing-evidence.json"
    queue_path = tmp_path / "review-queue.json"
    listing_path.write_text(
        json.dumps(_listing(_card("2026030377")), sort_keys=True), encoding="utf-8",
    )
    before = hashlib.sha256(listing_path.read_bytes()).hexdigest()
    result = runner.invoke(
        app, [
            "discover-preview", "--listing-evidence", str(listing_path),
            "--output", str(queue_path),
        ],
    )
    assert result.exit_code == 0, result.output
    summary = json.loads(result.stdout)
    assert summary["listing_artifact_sha256"] == before
    assert summary["candidate_count"] == 1
    assert summary["candidates"][0]["sch_number"] == "2026030377"
    assert summary["network_executed"] is False
    assert summary["persistence_mutated"] is False
    retained = json.loads(queue_path.read_text("utf-8"))
    assert retained["listing_artifact_sha256"] == before
    assert retained["candidate_count"] == 1
    assert hashlib.sha256(listing_path.read_bytes()).hexdigest() == before
    assert not (tmp_path / "operator.sqlite3").exists()
    second = runner.invoke(
        app, [
            "discover-preview", "--listing-evidence", str(listing_path),
            "--output", str(queue_path),
        ],
    )
    assert second.exit_code != 0
    assert json.loads(queue_path.read_text("utf-8")) == retained


def test_discover_preview_cli_blocks_bad_snapshot_without_queue(
    tmp_path: Path,
) -> None:
    listing_path = tmp_path / "listing-incomplete.json"
    queue_path = tmp_path / "must-not-appear.json"
    listing = _listing(_card("2026030377"))
    listing["snapshots"][0]["body_truncated"] = True
    listing_path.write_text(json.dumps(listing), encoding="utf-8")
    result = runner.invoke(
        app, [
            "discover-preview", "--listing-evidence", str(listing_path),
            "--output", str(queue_path),
        ],
    )
    assert result.exit_code == 1
    assert not queue_path.exists()
