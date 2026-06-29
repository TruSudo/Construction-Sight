import pytest
from pydantic import ValidationError

from constructionsight.parcel_row_preview_models import (
    ParcelRowPreview,
    ParcelRowPreviewInput,
    ParcelRowPreviewReport,
    ParcelRowPreviewStatus,
)
from constructionsight.parcel_schema_models import ParcelFieldRoleMatch
from constructionsight.parcel_source_models import (
    ParcelFieldRole,
    ParcelGeometrySupport,
    ParcelSourceFormat,
)


def test_row_preview_input_requires_rows_or_mappings() -> None:
    with pytest.raises(ValidationError):
        ParcelRowPreviewInput(
            source_key="test:source",
            source_name="Test Source",
            source_format=ParcelSourceFormat.CSV,
        )


def test_row_preview_input_rejects_blank_row_keys() -> None:
    with pytest.raises(ValidationError):
        ParcelRowPreviewInput(
            source_key="test:source",
            source_name="Test Source",
            source_format=ParcelSourceFormat.CSV,
            rows=[{"": "bad"}],
        )


def test_unusable_row_requires_limitation() -> None:
    with pytest.raises(ValidationError):
        ParcelRowPreview(row_number=1, usable=False)


def test_row_preview_report_requires_count_consistency() -> None:
    with pytest.raises(ValidationError):
        ParcelRowPreviewReport(
            preview_id="parcel-row-preview:test",
            source_key="test:source",
            source_name="Test Source",
            source_format=ParcelSourceFormat.CSV,
            status=ParcelRowPreviewStatus.READY_FOR_PARCEL_RECORD_MODEL,
            row_count=2,
            usable_row_count=1,
            skipped_row_count=0,
            rows=[ParcelRowPreview(row_number=1, usable=True)],
            next_action="test",
        )


def test_row_preview_report_accepts_empty_source_status() -> None:
    report = ParcelRowPreviewReport(
        preview_id="parcel-row-preview:test",
        source_key="test:source",
        source_name="Test Source",
        source_format=ParcelSourceFormat.CSV,
        status=ParcelRowPreviewStatus.EMPTY_SOURCE,
        row_count=0,
        usable_row_count=0,
        skipped_row_count=0,
        next_action="provide rows",
    )

    assert report.status == ParcelRowPreviewStatus.EMPTY_SOURCE


def test_row_preview_input_accepts_mapped_roles() -> None:
    preview_input = ParcelRowPreviewInput(
        source_key="test:source",
        source_name="Test Source",
        source_format=ParcelSourceFormat.CSV,
        field_role_matches=[
            ParcelFieldRoleMatch(
                source_field="APN",
                field_role=ParcelFieldRole.APN,
                match_reason="test",
                confidence_score=90,
            )
        ],
        geometry_support=ParcelGeometrySupport.CENTROID,
    )

    assert preview_input.field_role_matches[0].field_role == ParcelFieldRole.APN
