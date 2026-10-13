"""End-to-end offline SMARTS source review contract tests."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from constructionsight.smarts_snapshot_diff import SmartsSnapshotError
from constructionsight.smarts_source_review_cli import main, prepare_source_review


def _csv(path: Path, fields: tuple[str, ...], rows: list[tuple[str, ...]]) -> Path:
    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(fields)
    writer.writerows(rows)
    path.write_text(text.getvalue(), encoding="utf-8")
    return path


def test_combined_review_reports_change_plus_independent_inspection(
    tmp_path: Path,
) -> None:
    facility_fields = ("APP_ID", "WDID", "SITE_COUNTY", "STATUS")
    before = _csv(
        tmp_path / "before.csv", facility_fields,
        [("101", "8 33C101", "Riverside", "Active")],
    )
    after = _csv(
        tmp_path / "after.csv", facility_fields,
        [("101", "8 33C101", "Riverside", "Terminated")],
    )
    inspections = _csv(
        tmp_path / "inspections.csv",
        ("APP_ID", "WDID", "INSPECTION_ID", "INSPECTION_DATE", "PLACE_COUNTY", "PERMIT_TYPE"),
        [("101", "8 33C101", "10", "2026-09-01", "Riverside", "Construction")],
    )
    envelope = prepare_source_review(
        county="Riverside", previous=before, current=after, inspections=inspections
    )
    assert envelope["facility_change_review"]["counts"]["changed"] == 1
    assert envelope["inspection_review"]["linked_inspection_rows"] == 1
    assert envelope["site_identity"] == "source_scoped_only"
    assert envelope["physical_construction_verified"] is False
    assert envelope["application_graph_writes"] is False
    assert envelope["outreach"] is False
    assert envelope["bid_actions"] is False


def test_combined_review_without_optional_inspections(
    tmp_path: Path,
) -> None:
    headers = ("APP_ID", "WDID", "SITE_COUNTY")
    before = _csv(tmp_path / "before.csv", headers, [("101", "8 33C101", "Riverside")])
    after = _csv(tmp_path / "after.csv", headers, [("101", "8 33C101", "Riverside")])
    envelope = prepare_source_review(county="Riverside", previous=before, current=after)
    assert envelope["inspection_review"] is None
    assert envelope["facility_change_review"]["counts"]["unchanged"] == 1


def test_combined_review_rejects_same_file_twice(tmp_path: Path) -> None:
    snapshot = _csv(
        tmp_path / "same.csv", ("APP_ID", "WDID", "SITE_COUNTY"),
        [("101", "8 33C101", "Riverside")],
    )
    with pytest.raises(SmartsSnapshotError, match="separate retained"):
        prepare_source_review(county="Riverside", previous=snapshot, current=snapshot)


def test_combined_cli_is_json_and_fail_closed(
    capsys: pytest.CaptureFixture[str], tmp_path: Path,
) -> None:
    headers = ("APP_ID", "WDID", "SITE_COUNTY")
    before = _csv(tmp_path / "before.csv", headers, [("101", "8 33C101", "Riverside")])
    after = _csv(tmp_path / "after.csv", headers, [("101", "8 33C101", "Riverside")])
    args = ["--county", "Riverside", "--previous", str(before), "--current", str(after)]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["lead_readiness"] == "blocked_pending_independent_verification"
    assert main([
        "--county", "Riverside", "--previous", str(before), "--current", str(before)
    ]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
