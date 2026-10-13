"""Offline, source-neutral SMARTS capture integrity and atomic replay contracts."""

from __future__ import annotations

import csv
import hashlib
import io
import sqlite3
from pathlib import Path

import pytest

from constructionsight import smarts_snapshot_history as history
from constructionsight.smarts_snapshot_history import (
    SmartsHistoryError,
    append_snapshot,
    main,
    review_snapshot_changes,
    verify_snapshot_history,
)

_FIELDS = ("_id", "APP_ID", "WDID", "SITE_COUNTY", "STATUS", "CONTACT_EMAIL")


def _csv(
    path: Path, rows: list[tuple[str, str, str, str, str, str]]
) -> Path:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(_FIELDS)
    writer.writerows(rows)
    path.write_text(output.getvalue(), encoding="utf-8")
    path.chmod(0o600)
    return path


def _row(
    transport_id: str, app: str, *, county: str = "Riverside",
    status: str = "Active",
) -> tuple[str, str, str, str, str, str]:
    return (
        transport_id, app, "8 33C" + app, county, status,
        "private+contact@example.test",
    )


@pytest.fixture
def private(tmp_path: Path) -> tuple[Path, Path]:
    parent = tmp_path / "owner-only"
    parent.mkdir(mode=0o700)
    return parent, parent / "snapshots.sqlite3"


def test_baseline_replay_changed_missing_and_reappearance(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    first = _csv(root / "first.csv", [_row("1", "101"), _row("2", "102")])
    second = _csv(
        root / "second.csv",
        [_row("999", "101"), _row("4", "102", status="Terminated"), _row("5", "103")],
    )
    third = _csv(root / "third.csv", [_row("8", "101"), _row("9", "103")])
    fourth = _csv(
        root / "fourth.csv", [_row("8", "101"), _row("9", "103"), _row("10", "102")]
    )
    base = append_snapshot(ledger_path=db, csv_path=first, county="Riverside")
    assert base.baseline is True
    assert base.replayed is False
    assert (base.new, base.changed, base.missing_from_new) == (0, 0, 0)
    assert base.source_publication_verified is False
    assert base.commercial_actions_authorized is False
    assert verify_snapshot_history(db) == {
        "snapshots": 1, "source_rows": 2, "change_candidates": 0, "blobs": 1
    }

    second_result = append_snapshot(ledger_path=db, csv_path=second, county="Riverside")
    assert (
        second_result.new, second_result.changed,
        second_result.unchanged, second_result.missing_from_new
    ) == (1, 1, 1, 0)
    repeated = append_snapshot(ledger_path=db, csv_path=second, county="Riverside")
    assert repeated.replayed is True
    assert repeated.snapshot_id == second_result.snapshot_id
    assert verify_snapshot_history(db)["snapshots"] == 2

    missing = append_snapshot(ledger_path=db, csv_path=third, county="Riverside")
    assert missing.missing_from_new == 1
    assert missing.changed == 0
    revived = append_snapshot(ledger_path=db, csv_path=fourth, county="Riverside")
    assert revived.new == 1
    assert revived.changed == 0
    assert revived.county_coverage_verified is False
    integrity = verify_snapshot_history(db)
    assert integrity == {
        "snapshots": 4, "source_rows": 10, "change_candidates": 4, "blobs": 4
    }
    with sqlite3.connect(db) as connection:
        events = connection.execute(
            "SELECT outcome FROM snapshot_events ORDER BY snapshot_id,source_key"
        ).fetchall()
    assert [entry[0] for entry in events].count("missing_from_new") == 1
    assert [entry[0] for entry in events].count("new") == 2


def test_two_counties_share_original_file_without_combining_identity(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    source = _csv(
        root / "all-counties.csv",
        [_row("1", "101"), _row("2", "102", county="San Bernardino")],
    )
    san = append_snapshot(ledger_path=db, csv_path=source, county="San Bernardino")
    riv = append_snapshot(ledger_path=db, csv_path=source, county="Riverside")
    assert san.baseline is True and riv.baseline is True
    assert verify_snapshot_history(db) == {
        "snapshots": 2, "source_rows": 2, "change_candidates": 0, "blobs": 1
    }


def test_transport_only_renumbering_not_a_semantic_change(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    old = _csv(root / "old.csv", [_row("1", "101")])
    new = _csv(root / "new.csv", [_row("985", "101")])
    append_snapshot(ledger_path=db, csv_path=old, county="Riverside")
    receipt = append_snapshot(ledger_path=db, csv_path=new, county="Riverside")
    assert receipt.unchanged == 1
    assert (receipt.new, receipt.changed, receipt.missing_from_new) == (0, 0, 0)
    assert verify_snapshot_history(db)["change_candidates"] == 0


def test_alias_drift_fails_with_atomic_rollback(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    old = _csv(root / "old.csv", [_row("1", "101")])
    wrong = _csv(
        root / "wrong.csv",
        [("3", "999", "8 33C101", "Riverside", "Active", "hidden@example.test")],
    )
    append_snapshot(ledger_path=db, csv_path=old, county="Riverside")
    with pytest.raises(Exception, match="alias changed"):
        append_snapshot(ledger_path=db, csv_path=wrong, county="Riverside")
    assert verify_snapshot_history(db) == {
        "snapshots": 1, "source_rows": 1, "change_candidates": 0, "blobs": 1
    }


def test_missing_or_world_readable_csv_fails_without_creating_ledger(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    path = _csv(root / "public.csv", [_row("1", "101")])
    path.chmod(0o644)
    with pytest.raises(SmartsHistoryError, match="owner-only"):
        append_snapshot(ledger_path=db, csv_path=path, county="Riverside")
    assert not db.exists()
    path.chmod(0o600)
    with pytest.raises(SmartsHistoryError, match="cannot be read"):
        append_snapshot(ledger_path=db, csv_path=root / "missing.csv", county="Riverside")
    assert not db.exists()


def test_linked_source_file_is_rejected_without_creating_ledger(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    source = _csv(root / "original.csv", [_row("1", "101")])
    link = root / "linked.csv"
    link.symlink_to(source)
    with pytest.raises(SmartsHistoryError, match="owner-only"):
        append_snapshot(ledger_path=db, csv_path=link, county="Riverside")
    assert not db.exists()


def test_readonly_integrity_verification_never_creates_or_changes_file(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    with pytest.raises(SmartsHistoryError):
        verify_snapshot_history(db)
    assert not db.exists()
    first = _csv(root / "source.csv", [_row("1", "101")])
    append_snapshot(ledger_path=db, csv_path=first, county="Riverside")
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert verify_snapshot_history(db)["snapshots"] == 1
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before


def test_schema_drift_and_missing_immutability_trigger_fail_closed(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    csv_file = _csv(root / "source.csv", [_row("1", "101")])
    append_snapshot(ledger_path=db, csv_path=csv_file, county="Riverside")
    with sqlite3.connect(db) as con:
        con.execute("DROP TRIGGER snapshot_events_no_delete")
    with pytest.raises(SmartsHistoryError, match="immutability"):
        verify_snapshot_history(db)
    with pytest.raises(SmartsHistoryError, match="immutability"):
        append_snapshot(ledger_path=db, csv_path=csv_file, county="Riverside")


def test_orphaned_snapshots_rows_and_events_are_rejected(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    src = _csv(root / "source.csv", [_row("1", "101")])
    append_snapshot(ledger_path=db, csv_path=src, county="Riverside")
    with sqlite3.connect(db) as con:
        con.execute("PRAGMA foreign_keys=OFF")
        con.execute(
            "INSERT INTO snapshot_rows VALUES (?,?,?,?,?)",
            (99999, "smarts:facility:Riverside:wdid:8 33C999", "0" * 64, "999", "8 33C999"),
        )
    with pytest.raises(SmartsHistoryError, match="foreign-key integrity"):
        verify_snapshot_history(db)
    with pytest.raises(SmartsHistoryError, match="foreign-key integrity"):
        review_snapshot_changes(db)


def test_bad_publication_date_and_duplicate_source_id_do_not_write(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    source = _csv(root / "bad.csv", [_row("1", "101"), _row("2", "101")])
    with pytest.raises(SmartsHistoryError, match="strict facility"):
        append_snapshot(ledger_path=db, csv_path=source, county="Riverside")
    assert not db.exists()
    valid = _csv(root / "valid.csv", [_row("1", "101")])
    with pytest.raises(SmartsHistoryError, match="offset"):
        append_snapshot(
            ledger_path=db, csv_path=valid, county="Riverside",
            reported_publication_at="2026-10-02",
        )
    assert not db.exists()
    done = append_snapshot(
        ledger_path=db, csv_path=valid, county="Riverside",
        reported_publication_at="2026-10-02T08:00:00-07:00",
    )
    assert done.source_publication_verified is False
    assert verify_snapshot_history(db)["snapshots"] == 1


def test_cli_requires_explicit_retention_and_redacts_contact(
    private: tuple[Path, Path], capsys: pytest.CaptureFixture[str],
) -> None:
    root, db = private
    source = _csv(root / "input.csv", [_row("1", "101")])
    with pytest.raises(SystemExit):
        main(["--record", "--ledger", str(db), "--county", "Riverside", "--csv", str(source)])
    assert not db.exists()
    assert main([
        "--record", "--ledger", str(db), "--county", "Riverside",
        "--csv", str(source), "--retain-evidence",
    ]) == 0
    assert main(["--verify", "--ledger", str(db)]) == 0
    output = capsys.readouterr().out
    assert "private+contact@example.test" not in output
    assert "source_rows_exposed" in output
    assert '"source_completeness_verified": false' in output


def test_partial_write_failure_rolls_back_all_capture_rows(
    private: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, db = private
    source = _csv(root / "source.csv", [_row("1", "101")])

    class FailingTime:
        @staticmethod
        def now(_zone: object) -> object:
            raise RuntimeError("simulated failure after blob insertion")

        @staticmethod
        def fromisoformat(value: str) -> object:
            return history.datetime.fromisoformat(value)

    original_dt = history.datetime
    monkeypatch.setattr(history, "datetime", FailingTime)
    with pytest.raises(RuntimeError, match="simulated failure"):
        append_snapshot(ledger_path=db, csv_path=source, county="Riverside")
    monkeypatch.setattr(history, "datetime", original_dt)
    assert verify_snapshot_history(db) == {
        "snapshots": 0, "source_rows": 0, "change_candidates": 0, "blobs": 0
    }


def test_bounded_change_review_filters_sorts_and_redacts_private_rows(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    p = _csv(
        root / "first.csv",
        [_row("1", "101"), _row("2", "102"), _row("3", "103")],
    )
    q = _csv(
        root / "second.csv",
        [
            _row("99", "101", status="Terminated"),
            _row("98", "103"),
            _row("97", "104"),
        ],
    )
    append_snapshot(ledger_path=db, csv_path=p, county="Riverside")
    append_snapshot(ledger_path=db, csv_path=q, county="Riverside")
    baseline = review_snapshot_changes(db, county="Riverside", limit=2)
    assert baseline["schema_version"] == "constructionsight.smarts_change_review.v1"
    assert baseline["configured"] is True
    assert baseline["verified_private_history"] is True
    assert baseline["total"] == 3
    assert baseline["returned"] == 2
    assert baseline["has_more"] is True
    assert [x["outcome"] for x in baseline["items"]] == [
        "changed", "missing_from_new"
    ]
    assert [x["source_key"] for x in baseline["items"]] == [
        "smarts:facility:Riverside:wdid:8 33C101",
        "smarts:facility:Riverside:wdid:8 33C102",
    ]
    assert baseline["lead_readiness_authorized"] is False
    assert baseline["missing_is_deletion"] is False
    assert baseline["source_identity_is_project_identity"] is False
    import json

    assert "private+contact@example.test" not in json.dumps(baseline)
    nxt = review_snapshot_changes(db, county="Riverside", limit=2, offset=2)
    assert nxt["returned"] == 1
    assert nxt["items"][0]["outcome"] == "new"
    assert nxt["has_more"] is False
    assert review_snapshot_changes(db, county="San Bernardino")["total"] == 0
    assert review_snapshot_changes(db)["total"] == 3


def test_change_review_fail_closed_on_missing_invalid_or_altered_history(
    private: tuple[Path, Path],
) -> None:
    root, db = private
    assert review_snapshot_changes(None) == {
        "schema_version": "constructionsight.smarts_change_review.v1",
        "configured": False,
        "verified_private_history": False,
        "county_filter": "",
        "limit": 10,
        "offset": 0,
        "total": 0,
        "returned": 0,
        "has_more": False,
        "items": [],
        "read_only": True,
        "network_executed": False,
        "history_mutated": False,
        "raw_csv_exposed": False,
        "missing_is_deletion": False,
        "source_identity_is_project_identity": False,
        "parcel_or_project_matches_verified": False,
        "live_collection_enabled": False,
        "lead_readiness_authorized": False,
        "outreach_authorized": False,
        "bid_authorized": False,
    }
    with pytest.raises(SmartsHistoryError):
        review_snapshot_changes(db)
    assert not db.exists()
    for kwargs in (
        {"county": "Orange"}, {"limit": 26}, {"limit": 0}, {"offset": -1},
        {"limit": True}, {"offset": 1_000_001},
    ):
        with pytest.raises(SmartsHistoryError):
            review_snapshot_changes(db, **kwargs)
    p = _csv(root / "initial.csv", [_row("1", "101")])
    q = _csv(root / "second.csv", [_row("1", "101", status="Terminated")])
    append_snapshot(ledger_path=db, csv_path=p, county="Riverside")
    append_snapshot(ledger_path=db, csv_path=q, county="Riverside")
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    assert review_snapshot_changes(db)["total"] == 1
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    with sqlite3.connect(db) as con:
        con.execute("DROP TRIGGER snapshot_events_no_update")
    with pytest.raises(SmartsHistoryError, match="immutability"):
        review_snapshot_changes(db)
