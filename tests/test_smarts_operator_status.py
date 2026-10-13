"""SMARTS operator evidence status is opt-in, bounded, and never a write surface."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from constructionsight.operator_web import create_handler
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
from constructionsight.smarts_snapshot_history import append_snapshot
from constructionsight.storage.database import create_database_engine, initialize_database


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


def test_actual_loopback_endpoint_reads_only_selected_journal(tmp_path: Path) -> None:
    """Exercise the actual HTTP route and explicit opt-in configuration."""
    database = tmp_path / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    journal = _private_path(tmp_path)
    page = _page("Active")
    record_smarts_observation(
        journal, page, build_smarts_intake_preview(page, page.records[0])
    )
    before = hashlib.sha256(journal.read_bytes()).hexdigest()
    private_csv = journal.parent / "source.csv"
    private_csv.write_text(
        "_id,APP_ID,WDID,SITE_COUNTY,STATUS,CONTACT_EMAIL\\n"
        "1,101,8 33C101,Riverside,Active,private@example.test\\n",
        encoding="utf-8",
    )
    private_csv.chmod(0o600)
    csv_history = journal.parent / "history.sqlite3"
    append_snapshot(
        ledger_path=csv_history, csv_path=private_csv, county="Riverside"
    )
    history_digest = hashlib.sha256(csv_history.read_bytes()).hexdigest()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        create_handler(
            database, smarts_journal_path=journal,
            smarts_snapshot_history_path=csv_history,
        ),
    )
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]

        def get(path: str) -> tuple[int, dict[str, object]]:
            connection = HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                connection.request("GET", path, headers={"Host": f"127.0.0.1:{port}"})
                response = connection.getresponse()
                return response.status, json.loads(response.read())
            finally:
                connection.close()

        status, payload = get("/api/smarts-status")
        assert status == 200
        assert payload["journal_integrity_verified"] is True
        assert payload["observations"] == 1
        assert payload["semantic_versions"] == 1
        assert payload["source_identities"] == 1
        assert payload["csv_snapshot_history_configured"] is True
        assert payload["csv_snapshot_history_integrity_verified"] is True
        assert payload["csv_snapshots"] == 1
        assert payload["csv_source_row_observations"] == 1
        assert hashlib.sha256(csv_history.read_bytes()).hexdigest() == history_digest
        assert payload["network_executed"] is False
        assert payload["lead_readiness_authorized"] is False
        assert "private@example.test" not in json.dumps(payload)
        assert get("/api/smarts-status?county=Riverside")[0] == 400

        with sqlite3.connect(journal) as db:
            db.execute("ALTER TABLE smarts_observations ADD COLUMN unauthorized TEXT")
        failure_status, error = get("/api/smarts-status")
        assert failure_status == 503
        assert "private@example.test" not in json.dumps(error)
        assert "unauthorized" not in json.dumps(error)
        assert before != hashlib.sha256(journal.read_bytes()).hexdigest()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_csv_history_status_is_private_read_only_and_distinct_from_api_journal(
    tmp_path: Path,
) -> None:
    private = tmp_path / "owner-only"
    private.mkdir(mode=0o700)
    csv_path = private / "facilities.csv"
    csv_path.write_text(
        "_id,APP_ID,WDID,SITE_COUNTY,STATUS,CONTACT_EMAIL\n"
        "1,101,8 33C101,Riverside,Active,private@example.test\n",
        encoding="utf-8",
    )
    csv_path.chmod(0o600)
    history_path = private / "history.sqlite3"
    append_snapshot(
        ledger_path=history_path, csv_path=csv_path, county="Riverside"
    )
    before = hashlib.sha256(history_path.read_bytes()).hexdigest()
    result = build_smarts_operator_status(None, history_path)
    assert result["configured"] is False
    assert result["journal_integrity_verified"] is False
    assert result["csv_snapshot_history_configured"] is True
    assert result["csv_snapshot_history_integrity_verified"] is True
    assert result["csv_snapshots"] == 1
    assert result["csv_source_row_observations"] == 1
    assert result["csv_change_candidates"] == 0
    assert result["csv_original_blobs"] == 1
    assert result["county_coverage_verified"] is False
    assert result["lead_readiness_authorized"] is False
    assert "private@example.test" not in json.dumps(result)
    assert hashlib.sha256(history_path.read_bytes()).hexdigest() == before
