from pathlib import Path

import pytest

from constructionsight.parcel_schema_models import (
    ParcelObservedFieldType,
    ParcelSchemaField,
    ParcelSchemaPreviewInput,
    ParcelSchemaPreviewStatus,
)
from constructionsight.parcel_schema_preview import (
    load_schema_preview_input,
    preview_schema,
    preview_schema_for_source_key,
)
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSourceFormat,
)


def _regrid_like_input() -> ParcelSchemaPreviewInput:
    return ParcelSchemaPreviewInput(
        source_key="regrid:test",
        source_name="Regrid-like Test Source",
        source_format=ParcelSourceFormat.API_JSON,
        observed_fields=[
            ParcelSchemaField(source_field="parcelnumb", observed_type=ParcelObservedFieldType.STRING),
            ParcelSchemaField(source_field="county", observed_type=ParcelObservedFieldType.STRING),
            ParcelSchemaField(source_field="owner", observed_type=ParcelObservedFieldType.STRING),
            ParcelSchemaField(source_field="zoning", observed_type=ParcelObservedFieldType.STRING),
            ParcelSchemaField(source_field="geometry", observed_type=ParcelObservedFieldType.GEOMETRY),
            ParcelSchemaField(source_field="ll_updated_at", observed_type=ParcelObservedFieldType.DATETIME),
        ],
        geometry_support=ParcelGeometrySupport.POLYGON,
        spatial_reference="EPSG:4326",
        sample_record_count=3,
    )


def test_preview_schema_maps_regrid_like_fields() -> None:
    report = preview_schema(_regrid_like_input())
    mapped_roles = {match.field_role for match in report.mapped_fields}

    assert report.status == ParcelSchemaPreviewStatus.READY_FOR_IMPORT_PREVIEW
    assert ParcelFieldRole.APN in mapped_roles
    assert ParcelFieldRole.COUNTY in mapped_roles
    assert ParcelFieldRole.OWNER in mapped_roles
    assert ParcelFieldRole.ZONING in mapped_roles
    assert ParcelFieldRole.GEOMETRY in mapped_roles
    assert report.missing_required_roles == []
    assert report.next_action == "proceed to parcel import preview using this schema mapping"


def test_preview_schema_reports_missing_required_roles() -> None:
    preview_input = ParcelSchemaPreviewInput(
        source_key="test:missing-apn",
        source_name="Missing APN Test Source",
        source_format=ParcelSourceFormat.CSV,
        observed_fields=[
            ParcelSchemaField(source_field="owner_name"),
            ParcelSchemaField(source_field="situs_address"),
        ],
        geometry_support=ParcelGeometrySupport.CENTROID,
    )

    report = preview_schema(preview_input)

    assert report.status == ParcelSchemaPreviewStatus.MISSING_REQUIRED_FIELDS
    assert report.missing_required_roles == [ParcelFieldRole.APN, ParcelFieldRole.COUNTY]
    assert "missing required parcel roles: apn, county" in report.limitations


def test_preview_schema_tracks_unmapped_fields() -> None:
    preview_input = ParcelSchemaPreviewInput(
        source_key="test:unmapped",
        source_name="Unmapped Test Source",
        source_format=ParcelSourceFormat.CSV,
        observed_fields=[
            ParcelSchemaField(source_field="APN"),
            ParcelSchemaField(source_field="county"),
            ParcelSchemaField(source_field="mystery_field"),
        ],
        geometry_support=ParcelGeometrySupport.UNKNOWN,
    )

    report = preview_schema(preview_input)

    assert report.unmapped_fields == ["mystery_field"]
    assert "some observed fields were not mapped to canonical roles" in report.limitations
    assert "geometry support has not been verified" in report.limitations


def test_preview_schema_for_registered_source_key() -> None:
    report = preview_schema_for_source_key("regrid:licensed-parcel-provider")
    mapped_roles = {match.field_role for match in report.mapped_fields}

    assert report.source_key == "regrid:licensed-parcel-provider"
    assert ParcelFieldRole.APN in mapped_roles
    assert ParcelFieldRole.COUNTY in mapped_roles


def test_preview_schema_for_unknown_source_key_raises() -> None:
    with pytest.raises(ValueError, match="unknown parcel source key"):
        preview_schema_for_source_key("missing:source")


def test_load_schema_preview_input_from_json(tmp_path: Path) -> None:
    input_path = tmp_path / "schema-preview.json"
    input_path.write_text(_regrid_like_input().model_dump_json(), encoding="utf-8")

    loaded = load_schema_preview_input(input_path)

    assert loaded.source_key == "regrid:test"
    assert loaded.observed_fields[0].source_field == "parcelnumb"
