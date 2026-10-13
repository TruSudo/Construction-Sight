"""Offline SMARTS inspection-to-facility review regression contracts."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from constructionsight.smarts_inspection_review import (
    build_inspection_summary,
    main,
    review_inspections,
)
from constructionsight.smarts_snapshot_diff import (
    SmartsSnapshotError,
    load_facility_snapshot,
)

FAC_FIELDS = ("APP_ID", "WDID", "SITE_COUNTY", "SITE_NAME", "DEVELOPER_EMAIL")
INSP_FIELDS = (
    "APP_ID", "WDID", "INSPECTION_ID", "INSPECTION_DATE", "PLACE_COUNTY",
    "PERMIT_TYPE", "INSPECTION_STATUS", "INSPECTOR_NAME", "GENERAL_NOTES",
)


def _csv(path: Path, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> Path:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    path.write_text(output.getvalue(), encoding="utf-8")
    return path


def _facility(path: Path) -> Path:
    return _csv(
        path, FAC_FIELDS,
        [
            ("101", "8 33C101", "Riverside", "Alpha", "private@example.test"),
            ("102", "8 33C102", "Riverside", "Beta", "private2@example.test"),
        ],
    )


def _inspection(
    app: str, wdid: str, ident: str, *,
    county: str = "Riverside", permit: str = "Construction",
    when: str = "2026-09-12",
) -> tuple[str, ...]:
    return (
        app, wdid, ident, when, county, permit, "Completed",
        "Inspector Private Person", "Non-public review notes",
    )


def test_matching_inspections_summarized_without_raw_contacts(tmp_path: Path) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facility.csv"), county="Riverside")
    inspection_path = _csv(
        tmp_path / "inspection.csv", INSP_FIELDS,
        [
            _inspection("101.0", "8 33C101", "500"),
            _inspection("101", "8 33C101", "501", when="2026-10-01"),
            _inspection("102", "8 33C102", "502"),
        ],
    )
    review = review_inspections(inspection_path, facilities=facilities)
    summary = build_inspection_summary(facilities, review)
    assert summary["linked_inspection_rows"] == 3
    assert summary["linked_facility_count"] == 2
    assert summary["review_preview"][0]["latest_reported_inspection_date"] == "2026-10-01"
    assert summary["construction_activity_proven"] is False
    assert summary["security_demand_proven"] is False
    assert "Inspector Private Person" not in json.dumps(summary)
    assert "private@example.test" not in json.dumps(summary)
    assert "Non-public review notes" not in json.dumps(summary)


def test_fail_closed_alias_disagreement_and_unknown_secondary(
    tmp_path: Path,
) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facility.csv"), county="Riverside")
    inspections = _csv(
        tmp_path / "inspection.csv", INSP_FIELDS,
        [
            _inspection("101", "8 33C102", "1"),
            _inspection("101", "8 33C999", "2"),
            _inspection("999", "8 33C999", "3"),
            _inspection("101", "8 33C101", "4"),
        ],
    )
    summary = build_inspection_summary(
        facilities, review_inspections(inspections, facilities=facilities)
    )
    assert summary["identity_conflicts"] == 2
    assert summary["unmatched"] == 1
    assert summary["linked_inspection_rows"] == 1


def test_scope_and_county_are_not_equivalent_to_construction(
    tmp_path: Path,
) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facility.csv"), county="Riverside")
    inspections = _csv(
        tmp_path / "inspections.csv", INSP_FIELDS,
        [
            _inspection("101", "8 33C101", "1", permit="Industrial"),
            _inspection("101", "8 33C101", "4", permit="Non-Construction"),
            _inspection("101", "8 33C101", "2", county="San Bernardino"),
            _inspection("101", "8 33C101", "3", when="not a date"),
        ],
    )
    summary = build_inspection_summary(
        facilities, review_inspections(inspections, facilities=facilities)
    )
    assert summary["inspection_county_rows"] == 3
    assert summary["construction_inspection_rows"] == 1
    assert summary["out_of_scope_permit_type"] == 2
    assert summary["invalid_or_absent_dates_on_linked_rows"] == 1


def test_invalid_identifier_never_joins(tmp_path: Path) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facility.csv"), county="Riverside")
    inspections = _csv(
        tmp_path / "inspections.csv", INSP_FIELDS,
        [_inspection("101", "8 33C101", "NA")],
    )
    summary = build_inspection_summary(
        facilities, review_inspections(inspections, facilities=facilities)
    )
    assert summary["identity_conflicts"] == 1
    assert summary["linked_inspection_rows"] == 0


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facility.csv"), county="Riverside")
    inspections = _csv(
        tmp_path / "inspections.csv", INSP_FIELDS,
        [
            _inspection("101", "8 33C101", "1"),
            _inspection("102", "8 33C102", "1.00"),
        ],
    )
    with pytest.raises(SmartsSnapshotError, match="Duplicate inspection ID"):
        review_inspections(inspections, facilities=facilities)


@pytest.mark.parametrize("bad", [
    b"APP_ID,WDID,INSPECTION_ID,PLACE_COUNTY,PERMIT_TYPE\n",
    b"garbage\n",
    b"",
    b"\xff\xfe\x00",
])
def test_invalid_inspections_file_is_rejected(tmp_path: Path, bad: bytes) -> None:
    facilities = load_facility_snapshot(_facility(tmp_path / "facility.csv"), county="Riverside")
    path = tmp_path / "invalid.csv"
    path.write_bytes(bad)
    with pytest.raises(SmartsSnapshotError):
        review_inspections(path, facilities=facilities)


def test_cli_summary_only_and_same_file_blocked(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    facility_file = _facility(tmp_path / "facility.csv")
    inspection_file = _csv(
        tmp_path / "inspection.csv", INSP_FIELDS,
        [_inspection("101", "8 33C101", "1")],
    )
    args = [
        "--county", "Riverside", "--facilities", str(facility_file),
        "--inspections", str(inspection_file),
    ]
    assert main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["linked_inspection_rows"] == 1
    assert main([
        "--county", "Riverside", "--facilities", str(facility_file),
        "--inspections", str(facility_file),
    ]) == 1
