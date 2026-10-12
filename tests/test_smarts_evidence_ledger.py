"""Opt-in SMARTS evidence retention, identity alias and replay-safety contracts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from constructionsight.smarts_api import RESOURCE_IDS, SmartsPage
from constructionsight.smarts_evidence_ledger import (
    SmartsEvidenceError,
    record_smarts_observation,
    verify_smarts_journal,
)
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview


def _observation(**changes: Any) -> tuple[SmartsPage, Any]:
    record: dict[str, Any] = {
        "_id": 7,
        "APP_ID": "600752",
        "WDID": "8 33C413320",
        "SITE_COUNTY": "Riverside",
        "SITE_NAME": "Northern Gateway Street Improvements",
        "SITE_ADDRESS": "Evans Road and Barnett Road",
        "SITE_LATITUDE": "33.738514",
        "SITE_LONGITUDE": "-117.196525",
        "STATUS": "Active",
        "DEVELOPER_EMAIL": "sensitive@example.test",
    }
    record.update(changes)
    raw = json.dumps(
        {
            "success": True,
            "result": {
                "resource_id": RESOURCE_IDS["facilities"],
                "total": 1,
                "records": [record],
                "fields": [{"id": name} for name in record],
            },
        },
        separators=(",", ":"),
    ).encode()
    page = SmartsPage(
        resource="facilities",
        county="Riverside",
        offset=0,
        limit=2,
        total=1,
        request_url=(
            "https://publish.data.ca.gov/api/3/action/datastore_search?"
            "resource_id=8a0ed456-ca69-4b29-9c5b-5de3958dc963"
        ),
        response_sha256=hashlib.sha256(raw).hexdigest(),
        fields=tuple(record),
        records=(record,),
        raw_response_bytes=raw,
    )
    return page, build_smarts_intake_preview(page, record)


def _path(tmp_path: Path) -> Path:
    private = tmp_path / "private-smarts"
    private.mkdir(mode=0o700)
    return private / "evidence.sqlite3"


def test_immutable_original_response_and_duplicate_safe_replay(tmp_path: Path) -> None:
    path = _path(tmp_path)
    page, preview = _observation()
    first = record_smarts_observation(path, page, preview)
    second = record_smarts_observation(path, page, preview)
    assert first.outcome == "first_observation" and first.version == 1
    assert second.outcome == "unchanged" and second.version == 1
    assert second.observation_id != first.observation_id
    assert first.source_record_key == second.source_record_key
    assert verify_smarts_journal(path) == {"observations": 2, "versions": 1, "sources": 1}
    with sqlite3.connect(path) as conn:
        original = conn.execute(
            "SELECT raw_response FROM smarts_observations WHERE id=?", (first.observation_id,)
        ).fetchone()[0]
    assert original == page.raw_response_bytes
    assert b"sensitive@example.test" in original
    assert path.stat().st_mode & 0o777 == 0o600


def test_changed_then_reverted_record_creates_three_versions(tmp_path: Path) -> None:
    path = _path(tmp_path)
    initial, original = _observation()
    changed, revised = _observation(STATUS="Terminated")
    assert record_smarts_observation(path, initial, original).version == 1
    second = record_smarts_observation(path, changed, revised)
    assert second.outcome == "changed" and second.version == 2
    third = record_smarts_observation(path, initial, original)
    assert third.outcome == "changed" and third.version == 3
    assert verify_smarts_journal(path) == {"observations": 3, "versions": 3, "sources": 1}


def test_transport_row_renumbering_is_not_semantic_change(tmp_path: Path) -> None:
    path = _path(tmp_path)
    first, old = _observation(_id=7)
    revised, new = _observation(_id=99)
    assert record_smarts_observation(path, first, old).version == 1
    receipt = record_smarts_observation(path, revised, new)
    assert receipt.outcome == "unchanged" and receipt.version == 1
    assert verify_smarts_journal(path)["observations"] == 2


def test_conflicting_source_alias_fails_without_new_observation(tmp_path: Path) -> None:
    path = _path(tmp_path)
    first, original = _observation()
    record_smarts_observation(path, first, original)
    mismatched, wrong = _observation(WDID="9 33C000001")
    with pytest.raises(SmartsEvidenceError, match="unseen alias"):
        record_smarts_observation(path, mismatched, wrong)
    assert verify_smarts_journal(path) == {"observations": 1, "versions": 1, "sources": 1}


def test_ambiguous_existing_aliases_fail_closed(tmp_path: Path) -> None:
    path = _path(tmp_path)
    first, original = _observation()
    record_smarts_observation(path, first, original)
    second, new = _observation(APP_ID="777", WDID="9 33C000001")
    record_smarts_observation(path, second, new)
    conflict, preview = _observation(APP_ID="600752", WDID="9 33C000001")
    with pytest.raises(SmartsEvidenceError, match="Conflicting"):
        record_smarts_observation(path, conflict, preview)
    assert verify_smarts_journal(path) == {"observations": 2, "versions": 2, "sources": 2}


def test_missing_or_tampered_response_bytes_never_write(tmp_path: Path) -> None:
    path = _path(tmp_path)
    page, preview = _observation()
    object.__setattr__(page, "raw_response_bytes", b"not the actual bytes")
    with pytest.raises(SmartsEvidenceError, match="digest mismatch"):
        record_smarts_observation(path, page, preview)
    assert not path.exists()


def test_private_directory_enforced_and_symlink_denied(tmp_path: Path) -> None:
    page, preview = _observation()
    group_writable = tmp_path / "shared"
    group_writable.mkdir(mode=0o700)
    group_writable.chmod(0o770)
    with pytest.raises(SmartsEvidenceError, match="mode 0700"):
        record_smarts_observation(group_writable / "records.sqlite3", page, preview)
    private = tmp_path / "secure"
    private.mkdir(mode=0o700)
    outside = tmp_path / "outside.sqlite3"
    outside.write_bytes(b"outside")
    (private / "records.sqlite3").symlink_to(outside)
    with pytest.raises(SmartsEvidenceError, match="regular"):
        record_smarts_observation(private / "records.sqlite3", page, preview)
    assert outside.read_bytes() == b"outside"


def test_ledger_mutation_rejected_by_sqlite_triggers(tmp_path: Path) -> None:
    path = _path(tmp_path)
    page, preview = _observation()
    record_smarts_observation(path, page, preview)
    with sqlite3.connect(path) as conn, pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("DELETE FROM smarts_observations")
    assert verify_smarts_journal(path)["observations"] == 1


def test_missing_immutability_trigger_blocks_journal_reopen(tmp_path: Path) -> None:
    path = _path(tmp_path)
    page, preview = _observation()
    record_smarts_observation(path, page, preview)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TRIGGER smarts_observations_no_update")
    with pytest.raises(SmartsEvidenceError, match="immutability triggers"):
        verify_smarts_journal(path)


def test_failed_capture_does_not_advance_version(tmp_path: Path) -> None:
    path = _path(tmp_path)
    page, preview = _observation()
    record_smarts_observation(path, page, preview)
    changed, next_preview = _observation(STATUS="Terminated")
    object.__setattr__(changed, "response_sha256", "a" * 64)
    with pytest.raises(SmartsEvidenceError, match="digest mismatch"):
        record_smarts_observation(path, changed, next_preview)
    assert verify_smarts_journal(path) == {"observations": 1, "versions": 1, "sources": 1}
