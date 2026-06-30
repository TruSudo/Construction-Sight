import pytest

from constructionsight.parcel_core_models import ParcelGeometryKind
from constructionsight.parcel_record_builder import build_parcel_core_record_from_preview
from constructionsight.parcel_row_preview_models import ParcelRowPreview


def test_build_parcel_core_record_from_preview() -> None:
    row_preview = ParcelRowPreview(
        row_number=1,
        usable=True,
        normalized_apn="12345678",
        normalized_address="123 MAIN ST",
        county="Riverside",
        source_record_id="1",
    )

    record = build_parcel_core_record_from_preview(
        source_key="test:source",
        row_preview=row_preview,
        raw_geometry="POINT (-117.2 34.1)",
        spatial_reference="EPSG:4326",
    )

    assert record.parcel_record_id.startswith("parcel:")
    assert record.normalized_apn == "12345678"
    assert record.county == "Riverside"
    assert record.geometry is not None
    assert record.geometry.geometry_kind == ParcelGeometryKind.POINT


def test_build_parcel_core_record_rejects_unusable_preview() -> None:
    row_preview = ParcelRowPreview(
        row_number=1,
        usable=False,
        limitations=["missing APN value"],
    )

    with pytest.raises(ValueError, match="cannot build parcel core record"):
        build_parcel_core_record_from_preview(
            source_key="test:source",
            row_preview=row_preview,
        )


def test_build_parcel_core_record_requires_apn_and_county() -> None:
    row_preview = ParcelRowPreview(
        row_number=1,
        usable=True,
        normalized_apn="12345678",
    )

    with pytest.raises(ValueError, match="requires normalized APN and county"):
        build_parcel_core_record_from_preview(
            source_key="test:source",
            row_preview=row_preview,
        )
