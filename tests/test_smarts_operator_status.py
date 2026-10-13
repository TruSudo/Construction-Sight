"""SMARTS operator evidence status is opt-in, bounded, and never a write surface."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from constructionsight.smarts_api import RESOURCE_IDS, SmartsPage
from constructionsight.smarts_evidence_ledger import (
    SmartsEvidenceError,
    record_smarts_observation,
    verify_smarts_journal,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview
from constructionsight.smarts_operator_status import (
    SCHEMA_VERSION,
    build_smarts_operator_status,
)


def _page(status: str) -> SmartsPage:
    row = {
        "_id": 101,
        "APP_ID": "101",
        "WDID": "8 33C101",
        "SITE_COUNTY": "Riverside",
        "SITE_NAME": "Private test facility",
        "STATUS": status,
        "CONTACT_EMAIL": "private@example.test",
    }
    body = json.dumps(
        {
            "success": True,
            "result": {
                "resource_id": RESOURCE_IDS["facilities"],
                "total": 1,
                "records": [row],
                "fields": [{"id": field} for field in row],
            },
        },
        separators=(",", ":"),
    ).encode()
    return SmartsPage(
        "facilities", "Riverside", 0, 2, 1,
        "https://publish.data.ca.gov/api/3/action/datastore_search?resource_id="
        + RESOURCE_IDS["facilities"],
        hashlib.sha256(body).hexdigest(),
        tuple(row),
        (row,),
        body,
    )


def _private_path(tmp_path: Path) -> Path:
    parent = tmp_path / "owner-only"
    parent.mkdir(mode=0o700)
    return parent / "smarts.sqlite3"


def test_unconfigured_status_is_zero_and_never_claims_operational_authority() -> None:
    result = build_smarts_operator_status(None)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["configured"] is False
    assert result["journal_integrity_verified"] is False
    assert result["read_only"] is True
    assert result["network_executed"] is False
    assert result["source_rows_exposed"] is False
    assert result["observations"] == 0
    assert result["source_identities"] == 0
    assert result["scheduled_collection_enabled"] is False
    assert result["lead_readiness_authorized"] is False
    assert result["outreach_authorized"] is False
    assert result["bid_authorized"] is False


def test_selected_journal_is_verified_without_any_mutation(tmp_path: Path) -> None:
    path = _private_path(tmp_path)
    for state in ("Active", "Active", "Terminated"):
        page = _page(state)
        record_smarts_observation(
            path, page, build_smarts_intake_preview(page, page.records[0])
        )
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = build_smarts_operator_status(path)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["configured"] is True
    assert result["journal_integrity_verified"] is True
    assert (result["observations"], result["semantic_versions"], result["source_identities"]) == (
        3, 2, 1
    )
    assert result["county_coverage_verified"] is False
    assert result["parcel_or_project_matches_verified"] is False
    assert result["live_collection_enabled"] is False
    assert before == after
    assert "private@example.test" not in json.dumps(result)
    assert "Private test facility" not in json.dumps(result)


def test_read_only_open_never_creates_missing_file(tmp_path: Path) -> None:
    path = _private_path(tmp_path)
    with pytest.raises(SmartsEvidenceError, match="missing"):
        build_smarts_operator_status(path)
    assert not path.exists()
    with pytest.raises(SmartsEvidenceError, match="missing"):
        verify_smarts_journal(path, read_only=True)
    assert not path.exists()


def test_incompatible_or_unsafe_journal_fails_closed(tmp_path: Path) -> None:
    path = _private_path(tmp_path)
    page = _page("Active")
    record_smarts_observation(path, page, build_smarts_intake_preview(page, page.records[0]))
    with sqlite3.connect(path) as db:
        db.execute("ALTER TABLE smarts_observations ADD COLUMN unauthorized TEXT")
    with pytest.raises(SmartsEvidenceError, match="schema columns differ"):
        build_smarts_operator_status(path)


def test_world_readable_journal_refused(tmp_path: Path) -> None:
    path = _private_path(tmp_path)
    page = _page("Active")
    record_smarts_observation(path, page, build_smarts_intake_preview(page, page.records[0]))
    path.chmod(0o644)
    with pytest.raises(SmartsEvidenceError, match="mode 0600"):
        build_smarts_operator_status(path)
