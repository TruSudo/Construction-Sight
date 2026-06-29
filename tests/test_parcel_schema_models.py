import pytest
from pydantic import ValidationError

from constructionsight.parcel_schema_models import (
    ParcelFieldRoleMatch,
    ParcelSchemaField,
    ParcelSchemaPreviewInput,
    ParcelSchemaPreviewReport,
    ParcelSchemaPreviewStatus,
)
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSourceFormat,
)


def test_schema_preview_input_rejects_duplicate_fields() -> None:
    field = ParcelSchemaField(source_field="APN")

    with pytest.raises(ValidationError):
        ParcelSchemaPreviewInput(
            source_key="test:source",
            source_name="Test Source",
            source_format=ParcelSourceFormat.CSV,
            observed_fields=[field, field],
        )


def test_schema_preview_input_requires_field_or_geometry_signal() -> None:
    with pytest.raises(ValidationError):
        ParcelSchemaPreviewInput(
            source_key="test:source",
            source_name="Test Source",
            source_format=ParcelSourceFormat.CSV,
        )


def test_ready_schema_preview_rejects_missing_required_roles() -> None:
    with pytest.raises(ValidationError):
        ParcelSchemaPreviewReport(
            preview_id="parcel-schema-preview:test",
            source_key="test:source",
            source_name="Test Source",
            source_format=ParcelSourceFormat.CSV,
            status=ParcelSchemaPreviewStatus.READY_FOR_IMPORT_PREVIEW,
            observed_field_count=2,
            missing_required_roles=[ParcelFieldRole.APN],
            next_action="test",
        )


def test_missing_required_status_requires_missing_roles() -> None:
    with pytest.raises(ValidationError):
        ParcelSchemaPreviewReport(
            preview_id="parcel-schema-preview:test",
            source_key="test:source",
            source_name="Test Source",
            source_format=ParcelSourceFormat.CSV,
            status=ParcelSchemaPreviewStatus.MISSING_REQUIRED_FIELDS,
            observed_field_count=2,
            next_action="test",
        )


def test_field_role_match_accepts_required_role_marker() -> None:
    match = ParcelFieldRoleMatch(
        source_field="parcelnumb",
        field_role=ParcelFieldRole.APN,
        match_reason="exact field-name match: parcelnumb",
        confidence_score=95,
        required_role=True,
    )

    assert match.required_role is True
    assert match.field_role == ParcelFieldRole.APN


def test_schema_preview_field_rejects_duplicate_sample_values() -> None:
    with pytest.raises(ValidationError):
        ParcelSchemaField(
            source_field="APN",
            sample_values=["123", "123"],
        )


def test_schema_preview_input_accepts_geometry_only_signal() -> None:
    preview_input = ParcelSchemaPreviewInput(
        source_key="test:source",
        source_name="Test Source",
        source_format=ParcelSourceFormat.GEOJSON,
        geometry_support=ParcelGeometrySupport.POLYGON,
    )

    assert preview_input.geometry_support == ParcelGeometrySupport.POLYGON
