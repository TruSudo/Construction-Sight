from pathlib import Path

from constructionsight.parcel_row_preview import load_row_preview_input, preview_rows
from constructionsight.parcel_row_preview_models import (
    ParcelRowPreviewInput,
    ParcelRowPreviewStatus,
)
from constructionsight.parcel_schema_models import ParcelFieldRoleMatch
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSourceFormat,
)


def _match(source_field: str, role: ParcelFieldRole) -> ParcelFieldRoleMatch:
    return ParcelFieldRoleMatch(
        source_field=source_field,
        field_role=role,
        match_reason="test mapping",
        confidence_score=95,
        required_role=role in {ParcelFieldRole.APN, ParcelFieldRole.COUNTY},
    )


def _preview_input() -> ParcelRowPreviewInput:
    return ParcelRowPreviewInput(
        source_key="test:parcel-rows",
        source_name="Parcel Row Test Source",
        source_format=ParcelSourceFormat.CSV,
        field_role_matches=[
            _match("APN", ParcelFieldRole.APN),
            _match("County", ParcelFieldRole.COUNTY),
            _match("Address", ParcelFieldRole.ADDRESS),
            _match("OBJECTID", ParcelFieldRole.SOURCE_RECORD_ID),
            _match("geometry", ParcelFieldRole.GEOMETRY),
        ],
        rows=[
            {
                "APN": "123-456-78",
                "County": "San Bernardino",
                "Address": " 123 Main St ",
                "OBJECTID": "1",
                "geometry": "shape-present",
            },
            {
                "APN": "",
                "County": "San Bernardino",
                "Address": "456 Main St",
                "OBJECTID": "2",
                "geometry": "",
            },
        ],
        geometry_support=ParcelGeometrySupport.POLYGON,
        spatial_reference="EPSG:4326",
    )


def test_preview_rows_normalizes_and_counts_rows() -> None:
    report = preview_rows(_preview_input())
    first_row = report.rows[0]
    second_row = report.rows[1]

    assert report.status == ParcelRowPreviewStatus.ROW_ISSUES
    assert report.row_count == 2
    assert report.usable_row_count == 1
    assert report.skipped_row_count == 1
    assert first_row.normalized_apn == "12345678"
    assert first_row.normalized_address == "123 MAIN ST"
    assert first_row.source_record_id == "1"
    assert first_row.geometry_present is True
    assert second_row.usable is False
    assert second_row.limitations == ["missing APN value"]


def test_preview_rows_requires_required_mapped_roles() -> None:
    preview_input = ParcelRowPreviewInput(
        source_key="test:missing-county-map",
        source_name="Missing County Mapping Source",
        source_format=ParcelSourceFormat.CSV,
        field_role_matches=[_match("APN", ParcelFieldRole.APN)],
        rows=[{"APN": "123"}],
    )

    report = preview_rows(preview_input)

    assert report.status == ParcelRowPreviewStatus.NEEDS_SCHEMA_MAPPING
    assert "missing required mapped roles: county" in report.limitations


def test_preview_rows_reports_empty_source() -> None:
    preview_input = ParcelRowPreviewInput(
        source_key="test:empty",
        source_name="Empty Source",
        source_format=ParcelSourceFormat.CSV,
        field_role_matches=[
            _match("APN", ParcelFieldRole.APN),
            _match("County", ParcelFieldRole.COUNTY),
        ],
        rows=[],
    )

    report = preview_rows(preview_input)

    assert report.status == ParcelRowPreviewStatus.EMPTY_SOURCE
    assert report.next_action == "provide sample rows before building ParcelRecord objects"


def test_load_row_preview_input_from_json(tmp_path: Path) -> None:
    input_path = tmp_path / "row-preview.json"
    input_path.write_text(_preview_input().model_dump_json(), encoding="utf-8")

    loaded = load_row_preview_input(input_path)

    assert loaded.source_key == "test:parcel-rows"
    assert loaded.rows[0]["APN"] == "123-456-78"
