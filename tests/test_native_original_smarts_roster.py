"""Native original SMARTS roster verification is offline and always source-only."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.command_center_smarts_roster import (
    original_retained_smarts_roster_audit,
)
from constructionsight.live_command_center import make_server
from constructionsight.smarts_collection import (
    _roster_digest,
    collect_roster,
    parse_roster,
)
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_native_original_ceqanet_maturity import _retained
from tests.test_smarts_collection import _page


def _roster(tmp_path: Path) -> tuple[Path, Path, Path]:
    db, _ceqa_evidence, folder = _retained(tmp_path)
    roster = folder / "smarts-roster.json"
    roster.write_text(json.dumps([
        {"county": "San Bernardino", "app_id": "602979"},
        {"county": "Riverside", "wdid": "8 33C123456"},
    ]), encoding="utf-8")
    return db, roster, folder


def test_native_original_smarts_roster_matches_source_contract_without_effect(
    tmp_path: Path,
) -> None:
    db, roster, _ = _roster(tmp_path)
    before = roster.read_bytes()
    before_db = hashlib.sha256(db.read_bytes()).hexdigest()
    value = original_retained_smarts_roster_audit(roster, None)
    assert value["available"] is True
    assert value["roster_count"] == 2
    assert value["original_roster_digest"] == _roster_digest(parse_roster(before))
    assert value["exact_facility_targets"][0]["exact_identifier"] == "602979"
    assert value["source_journal_status"] == "not_configured"
    assert not any(value[k] for k in (
        "network_executed", "collector_executed", "checkpoint_created",
        "journal_mutated", "schedule_activated",
        "live_source_access_authorized", "commercial_authority_granted",
    ))
    assert roster.read_bytes() == before
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_db


def test_native_original_roster_denies_invalid_scope_and_symlink(
    tmp_path: Path,
) -> None:
    _db, roster, folder = _roster(tmp_path)
    assert original_retained_smarts_roster_audit(None, None)["available"] is False
    original = roster.read_bytes()
    roster.write_text('[{"county":"Orange","app_id":"123"}]')
    with pytest.raises(ValueError):
        original_retained_smarts_roster_audit(roster, None)
    roster.write_bytes(original)
    linked = folder / "linked-roster.json"
    linked.symlink_to(roster)
    with pytest.raises(ValueError, match="original SMARTS roster must not be a symbolic link"):
        original_retained_smarts_roster_audit(linked, None)


def test_original_smarts_roster_native_get_denies_unconfigured_post_and_query(
    tmp_path: Path,
) -> None:
    db, roster, folder = _roster(tmp_path)
    server = make_server(
        snapshot(), 0, folder,
        operator_database=db,
        operator_smarts_collection_roster=roster,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            got = client.get("/api/source-smarts-roster-audit")
            assert got.status_code == 200, got.text
            assert got.json()["original_roster_integrity_verified"] is True
            assert client.get(
                "/api/source-smarts-roster-audit?collect=1"
            ).status_code == 409
            assert client.post(
                "/api/source-smarts-roster-audit", json={"execute_live": True},
                headers={"Origin": host},
            ).status_code == 501
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_original_roster_launcher_requires_real_file_and_data(tmp_path: Path) -> None:
    db, roster, folder = _roster(tmp_path)
    with pytest.raises(ValueError, match="requires real operator data"):
        make_server(
            snapshot(), 0, folder,
            operator_smarts_collection_roster=roster,
        )
    linked = folder / "roster-link.json"
    linked.symlink_to(roster)
    with pytest.raises(ValueError, match="existing regular file"):
        make_server(
            snapshot(), 0, folder,
            operator_database=db,
            operator_smarts_collection_roster=linked,
        )


def test_original_roster_configured_journal_is_verified_without_write(
    tmp_path: Path,
) -> None:
    _db, roster, folder = _roster(tmp_path)
    journal = folder / "smarts-source-evidence.sqlite3"
    checkpoint = folder / "smarts-collection-checkpoint.sqlite3"
    targets = parse_roster(roster.read_bytes())
    result = collect_roster(
        run_id="roster-audit-fixture",
        targets=targets,
        journal_path=journal,
        checkpoint_path=checkpoint,
        max_requests=2,
        fetch=lambda target: _page(
            target.app_id or "123456",
            wdid=target.wdid,
            county=target.county,
        ),
    )
    assert result.completed == 2
    original_bytes = journal.read_bytes()
    checkpoint_bytes = checkpoint.read_bytes()
    review = original_retained_smarts_roster_audit(roster, journal)
    assert review["original_source_journal_integrity_verified"] is True
    assert review["source_journal_status"] == "original_integrity_verified"
    assert review["journal_mutated"] is False
    assert journal.read_bytes() == original_bytes
    assert checkpoint.read_bytes() == checkpoint_bytes
