"""Offline SMARTS compliance source identity and non-promotion regression tests."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from constructionsight.smarts_compliance_review import (
    build_compliance_summary,
    main,
    review_compliance,
)
from constructionsight.smarts_snapshot_diff import (
    SmartsSnapshotError,
    load_facility_snapshot,
)


def _file(path: Path, columns: tuple[str, ...], rows: list[tuple[str, ...]]) -> Path:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(columns)
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8")
    return path


def _facility(path: Path) -> Path:
    return _file(
        path, ("APP_ID", "WDID", "SITE_COUNTY", "DEVELOPER_EMAIL"),
        [("101", "8 33C101", "Riverside", "private@example.test")],
    )


@pytest.mark.parametrize(
    ("kind", "key", "when"),
    [
        ("violations", "VIOLATION_ID", "OCCURRENCE_DATE"),
        ("enforcement", "ENFORCEMENT_ID", "ISSUANCE_DATE"),
    ],
)
def test_compliance_link_and_no_liability_promotion(
    tmp_path: Path, kind: str, key: str, when: str
) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facilities.csv"), county="Riverside")
    source = _file(
        tmp_path / "source.csv",
        ("APP_ID", "WDID", key, when, "PLACE_COUNTY", "PERMIT_TYPE", "DESCRIPTION"),
        [
            ("101", "8 33C101", "1001", "2026-09-01", "Riverside", "Construction",
             "Confidential irrelevant notes"),
            ("101", "8 33C999", "1002", "2026-09-01", "Riverside", "Construction",
             "Must not join"),
            ("101", "8 33C101", "1003", "2026-09-01", "Riverside", "Industrial",
             "Wrong program"),
        ],
    )
    # Type narrowing comes from a controlled parametric test, not untrusted CLI.
    assert kind in ("violations", "enforcement")
    review = review_compliance(source, kind=kind, facilities=facilities)
    summary = build_compliance_summary(facilities, review)
    assert summary["linked_records"] == 1
    assert summary["identity_conflicts"] == 1
    assert summary["out_of_scope_permit_type"] == 1
    assert summary["regulatory_findings_adjudicated"] is False
    assert summary["physical_construction_verified"] is False
    assert "Confidential irrelevant notes" not in json.dumps(summary)
    assert "private@example.test" not in json.dumps(summary)


def test_duplicate_source_id_is_rejected(tmp_path: Path) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facility.csv"), county="Riverside")
    source = _file(
        tmp_path / "bad.csv",
        ("APP_ID", "WDID", "VIOLATION_ID", "OCCURRENCE_DATE", "PLACE_COUNTY", "PERMIT_TYPE"),
        [
            ("101", "8 33C101", "1", "2026-09-01", "Riverside", "Construction"),
            ("101", "8 33C101", "1.0", "2026-09-01", "Riverside", "Construction"),
        ],
    )
    with pytest.raises(SmartsSnapshotError, match="Duplicate compliance"):
        review_compliance(source, kind="violations", facilities=facilities)


def test_cli_resource_specific_missing_columns_fails(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    facility = _facility(tmp_path / "facility.csv")
    source = _file(
        tmp_path / "bad.csv",
        ("APP_ID", "WDID", "VIOLATION_ID", "OCCURRENCE_DATE", "PLACE_COUNTY", "PERMIT_TYPE"),
        [("101", "8 33C101", "1", "2026-09-01", "Riverside", "Construction")],
    )
    assert main([
        "--county", "Riverside", "--facilities", str(facility),
        "--resource", "enforcement", "--compliance", str(source),
    ]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
