"""Offline restart and failure contracts for explicit SMARTS roster sweeps."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from constructionsight import smarts_collection
from constructionsight.smarts_api import RESOURCE_IDS, SmartsPage
from constructionsight.smarts_collection import (
    FacilityTarget,
    SmartsCollectionError,
    collect_roster,
    parse_roster,
)
from constructionsight.smarts_evidence_ledger import SmartsEvidenceError, verify_smarts_journal


def _page(
    app_id: str, *, status: str = "Active", wdid: str | None = None, county: str = "Riverside"
) -> SmartsPage:
    row: dict[str, Any] = {
        "_id": int(app_id),
        "APP_ID": app_id,
        "WDID": wdid or "8 33C" + app_id,
        "SITE_COUNTY": county,
        "SITE_NAME": "Test facility",
        "STATUS": status,
        "DEVELOPER_EMAIL": "private@example.test",
    }
    body = json.dumps(
        {
            "success": True,
            "result": {
                "resource_id": RESOURCE_IDS["facilities"],
                "total": 1,
                "records": [row],
                "fields": [{"id": name} for name in row],
            },
        },
        separators=(",", ":"),
    ).encode()
    return SmartsPage(
        "facilities",
        county,
        0,
        2,
        1,
        "https://publish.data.ca.gov/api/3/action/datastore_search?resource_id="
        + RESOURCE_IDS["facilities"],
        hashlib.sha256(body).hexdigest(),
        tuple(row),
        (row,),
        body,
    )


@pytest.fixture
def paths(tmp_path: Path) -> tuple[Path, Path]:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    return private / "evidence.sqlite3", private / "checkpoint.sqlite3"


def _collect(
    paths: tuple[Path, Path],
    run: str,
    targets: tuple[FacilityTarget, ...],
    fetch: Any,
    budget: int = 25,
) -> Any:
    return collect_roster(
        run_id=run,
        targets=targets,
        journal_path=paths[0],
        checkpoint_path=paths[1],
        max_requests=budget,
        fetch=fetch,
    )


def test_bounded_resume_and_new_sweep_reconcile_changes(paths: tuple[Path, Path]) -> None:
    targets = (FacilityTarget("Riverside", app_id="101"), FacilityTarget("Riverside", app_id="102"))
    first = _collect(paths, "sweep-1", targets, lambda t: _page(t.app_id or ""), 1)
    assert (first.completed, first.requests, first.first_observations) == (1, 1, 1)
    second = _collect(paths, "sweep-1", targets, lambda t: _page(t.app_id or ""))
    assert (second.completed, second.requests, second.first_observations) == (2, 1, 1)
    assert (
        _collect(paths, "sweep-1", targets, lambda _: pytest.fail("completed run fetched")).requests
        == 0
    )
    revised = _collect(
        paths,
        "sweep-2",
        targets,
        lambda t: _page(t.app_id or "", status="Terminated" if t.app_id == "101" else "Active"),
    )
    assert (revised.changed, revised.unchanged) == (1, 1)
    assert verify_smarts_journal(paths[0]) == {"observations": 4, "versions": 3, "sources": 2}


def test_partial_failure_retries_only_failed_target(paths: tuple[Path, Path]) -> None:
    targets = (FacilityTarget("Riverside", app_id="101"), FacilityTarget("Riverside", app_id="102"))

    def fail_second(target: FacilityTarget) -> SmartsPage:
        if target.app_id == "102":
            raise RuntimeError("offline transport failure")
        return _page("101")

    with pytest.raises(RuntimeError, match="transport"):
        _collect(paths, "partial", targets, fail_second)
    with sqlite3.connect(paths[1]) as db:
        assert db.execute("SELECT next_index FROM collection_runs").fetchone() == (1,)
    called: list[str | None] = []

    def resume(target: FacilityTarget) -> SmartsPage:
        called.append(target.app_id)
        return _page(target.app_id or "")

    assert _collect(paths, "partial", targets, resume).completed == 2
    assert called == ["102"]
    assert verify_smarts_journal(paths[0])["observations"] == 2


def test_crash_after_evidence_commit_replays_without_new_version(
    paths: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = (FacilityTarget("Riverside", app_id="101"),)
    original = smarts_collection.record_smarts_observation

    def crash_after_commit(*args: Any, **kwargs: Any) -> Any:
        original(*args, **kwargs)
        raise RuntimeError("simulated process loss after journal commit")

    monkeypatch.setattr(smarts_collection, "record_smarts_observation", crash_after_commit)
    with pytest.raises(RuntimeError, match="simulated"):
        _collect(paths, "replay", target, lambda _: _page("101"))
    monkeypatch.setattr(smarts_collection, "record_smarts_observation", original)
    result = _collect(paths, "replay", target, lambda _: _page("101"))
    assert (result.unchanged, result.completed) == (1, 1)
    assert verify_smarts_journal(paths[0]) == {"observations": 2, "versions": 1, "sources": 1}


def test_source_drift_and_alias_collision_never_advance(paths: tuple[Path, Path]) -> None:
    target = (FacilityTarget("Riverside", app_id="101"),)
    with pytest.raises(SmartsCollectionError, match="identity drifted"):
        _collect(paths, "drift", target, lambda _: _page("102"))
    with sqlite3.connect(paths[1]) as db:
        assert db.execute("SELECT next_index FROM collection_runs").fetchone() == (0,)
    _collect(paths, "drift", target, lambda _: _page("101"))
    # The same APP_ID with a new WDID is an alias conflict, not an update.
    with pytest.raises(SmartsEvidenceError, match="unseen alias"):
        _collect(paths, "alias", target, lambda _: _page("101", wdid="9 33C101"))
    with sqlite3.connect(paths[1]) as db:
        assert db.execute(
            "SELECT next_index FROM collection_runs WHERE run_id='alias'"
        ).fetchone() == (0,)
    assert verify_smarts_journal(paths[0])["observations"] == 1


def test_resume_rejects_changed_manifest_and_missing_receipt(paths: tuple[Path, Path]) -> None:
    target = (FacilityTarget("Riverside", app_id="101"),)
    _collect(paths, "bound", target, lambda _: _page("101"))
    with pytest.raises(SmartsCollectionError, match="binding changed"):
        _collect(
            paths,
            "bound",
            (FacilityTarget("Riverside", app_id="102"),),
            lambda _: pytest.fail("must not fetch"),
        )
    with sqlite3.connect(paths[1]) as db:
        db.execute("UPDATE collection_steps SET observation_id=999")
    with pytest.raises(SmartsCollectionError, match="receipt is missing"):
        _collect(paths, "bound", target, lambda _: pytest.fail("must not fetch"))


def test_invalid_page_and_tampered_body_leave_checkpoint_unadvanced(
    paths: tuple[Path, Path],
) -> None:
    target = (FacilityTarget("Riverside", app_id="101"),)
    wrong_county = _page("101", county="San Bernardino")
    with pytest.raises(SmartsCollectionError, match="wrong page"):
        _collect(paths, "invalid", target, lambda _: wrong_county)
    tampered = _page("101")
    object.__setattr__(tampered, "raw_response_bytes", b"tampered")
    with pytest.raises(SmartsEvidenceError, match="digest mismatch"):
        _collect(paths, "invalid", target, lambda _: tampered)
    with sqlite3.connect(paths[1]) as db:
        assert db.execute("SELECT next_index FROM collection_runs").fetchone() == (0,)


@pytest.mark.parametrize(
    "roster",
    [
        b"[]",
        b"not json",
        b'[{"county":"Riverside","app_id":"NA"}]',
        b'[{"county":"Riverside","app_id":"000"}]',
        b'[{"county":"Riverside","app_id":"101","wdid":"8 33C101"}]',
        b'[{"county":"Riverside","app_id":"101"},{"county":"Riverside","app_id":"101"}]',
        b'[{"county":"Los Angeles","app_id":"101"}]',
    ],
)
def test_invalid_rosters_rejected(roster: bytes) -> None:
    with pytest.raises(SmartsCollectionError):
        parse_roster(roster)


def test_new_run_cannot_skip_unfinished_run(paths: tuple[Path, Path]) -> None:
    targets = (FacilityTarget("Riverside", app_id="101"), FacilityTarget("Riverside", app_id="102"))
    _collect(paths, "unfinished", targets, lambda t: _page(t.app_id or ""), 1)
    with pytest.raises(SmartsCollectionError, match="prior collection run"):
        _collect(paths, "next", targets, lambda _: pytest.fail("must not fetch"))
