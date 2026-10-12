"""Read-only, offline and fail-closed SMARTS snapshot comparison contracts."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from constructionsight.smarts_snapshot_diff import (
    SmartsSnapshotError,
    build_review_summary,
    load_facility_snapshot,
    main,
    reconcile_snapshots,
)

FIELDS = ("_id", "APP_ID", "WDID", "SITE_COUNTY", "STATUS", "DEVELOPER_EMAIL")


def _save(path: Path, rows: list[tuple[str, ...]], fields: tuple[str, ...] = FIELDS) -> Path:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(fields)
    writer.writerows(rows)
    path.write_text(output.getvalue(), encoding="utf-8")
    return path


def _row(index: str, app: str, wdid: str, *, status: str = "Active") -> tuple[str, ...]:
    return (index, app, wdid, "Riverside", status, "private@example.test")


def test_change_detection_ignore_transport_id_and_redact_contact(
    tmp_path: Path,
) -> None:
    old = _save(
        tmp_path / "older.csv",
        [_row("1", "101", "8 33C101"), _row("2", "102", "8 33C102")],
    )
    new = _save(
        tmp_path / "newer.csv",
        [
            _row("999", "101", "8 33C101"),
            _row("10", "102", "8 33C102", status="Terminated"),
            _row("11", "103", "8 33C103"),
        ],
    )
    p = load_facility_snapshot(old, county="Riverside")
    c = load_facility_snapshot(new, county="Riverside")
    summary = build_review_summary(p, c, reconcile_snapshots(p, c))
    assert summary["counts"] == {
        "new": 1, "changed": 1, "unchanged": 1, "missing_from_new": 0,
    }
    assert summary["coverage_status"] == "unverified"
    assert "private@example.test" not in json.dumps(summary)
    assert summary["review_count"] == 2


def test_missing_is_review_only_not_deletion(tmp_path: Path) -> None:
    p = load_facility_snapshot(
        _save(
            tmp_path / "a.csv",
            [_row("1", "101", "8 33C101"), _row("2", "102", "8 33C102")],
        ),
        county="Riverside",
    )
    c = load_facility_snapshot(
        _save(tmp_path / "b.csv", [_row("1", "101", "8 33C101")]),
        county="Riverside",
    )
    summary = build_review_summary(p, c, reconcile_snapshots(p, c))
    counts = summary["counts"]
    assert isinstance(counts, dict)
    assert counts["missing_from_new"] == 1
    assert summary["missing_from_new_is_deletion"] is False


@pytest.mark.parametrize(
    "bad_rows",
    [
        [_row("1", "101", "8 33C101"), _row("2", "101", "8 33C102")],
        [_row("1", "101", "8 33C101"), _row("2", "102", "8 33C101")],
        [_row("1", "NA", "NA")],
        [_row("1", "0", "")],
        [_row("1", "abc", "8 33C101")],
    ],
)
def test_ambiguous_or_missing_source_identity_fails(
    tmp_path: Path, bad_rows: list[tuple[str, ...]]
) -> None:
    with pytest.raises(SmartsSnapshotError):
        load_facility_snapshot(_save(tmp_path / "bad.csv", bad_rows), county="Riverside")


def test_cross_snapshot_alias_drift_fails(tmp_path: Path) -> None:
    old = load_facility_snapshot(
        _save(tmp_path / "a.csv", [_row("1", "101", "8 33C101")]),
        county="Riverside",
    )
    new = load_facility_snapshot(
        _save(tmp_path / "b.csv", [_row("2", "101", "8 33C999")]),
        county="Riverside",
    )
    with pytest.raises(SmartsSnapshotError, match="identity drift"):
        reconcile_snapshots(old, new)


def test_stable_key_changed_alias_fails(tmp_path: Path) -> None:
    old = load_facility_snapshot(
        _save(tmp_path / "a.csv", [_row("1", "101", "8 33C101")]),
        county="Riverside",
    )
    new = load_facility_snapshot(
        _save(tmp_path / "b.csv", [_row("2", "102", "8 33C101")]),
        county="Riverside",
    )
    with pytest.raises(SmartsSnapshotError, match="alias changed"):
        reconcile_snapshots(old, new)


def test_schema_change_fails(tmp_path: Path) -> None:
    old = load_facility_snapshot(
        _save(tmp_path / "a.csv", [_row("1", "101", "8 33C101")]),
        county="Riverside",
    )
    new = load_facility_snapshot(
        _save(
            tmp_path / "b.csv",
            [("101", "8 33C101", "Riverside", "Active", "private@example.test")],
            FIELDS[1:],
        ),
        county="Riverside",
    )
    with pytest.raises(SmartsSnapshotError, match="schema changed"):
        reconcile_snapshots(old, new)


def test_multicounty_csv_only_selects_requested_county(tmp_path: Path) -> None:
    other = ("2", "103", "8 36C103", "San Bernardino", "Active", "someone@example.test")
    snapshot = load_facility_snapshot(
        _save(tmp_path / "all.csv", [_row("1", "101", "8 33C101"), other]),
        county="Riverside",
    )
    assert snapshot.total_rows == 2
    assert snapshot.selected_rows == 1


def test_csv_header_malformed_or_missing_selected_county(tmp_path: Path) -> None:
    invalid = tmp_path / "bad.csv"
    invalid.write_text("APP_ID,WDID,SITE_COUNTY,SITE_COUNTY\\n101,X,Riverside,Riverside\\n")
    with pytest.raises(SmartsSnapshotError, match="duplicate"):
        load_facility_snapshot(invalid, county="Riverside")
    invalid.write_text("APP_ID,WDID,SITE_COUNTY\\n101,8 33C101,San Bernardino\\n")
    with pytest.raises(SmartsSnapshotError, match="No records"):
        load_facility_snapshot(invalid, county="Riverside")


def test_cli_read_only_summary(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    old = _save(tmp_path / "a.csv", [_row("1", "101", "8 33C101")])
    new = _save(tmp_path / "b.csv", [_row("2", "101", "8 33C101")])
    code = main(["--county", "Riverside", "--previous", str(old), "--current", str(new)])
    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["counts"]["unchanged"] == 1
    assert output["previous_file_sha256"] != output["current_file_sha256"]
    assert main(["--county", "Riverside", "--previous", str(old), "--current", str(old)]) == 1
