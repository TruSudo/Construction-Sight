import pytest
from pydantic import ValidationError

from constructionsight.parcel_core_models import (
    ParcelCoreRecord,
    ParcelGeometry,
    ParcelGeometryKind,
)


def test_parcel_geometry_requires_raw_geometry_or_centroid() -> None:
    with pytest.raises(ValidationError):
        ParcelGeometry(geometry_kind=ParcelGeometryKind.UNKNOWN)


def test_parcel_geometry_accepts_centroid_only() -> None:
    geometry = ParcelGeometry(
        geometry_kind=ParcelGeometryKind.POINT,
        centroid_latitude=34.1,
        centroid_longitude=-117.2,
    )

    assert geometry.centroid_latitude == 34.1
    assert geometry.centroid_longitude == -117.2


def test_parcel_core_record_requires_matching_normalized_apn() -> None:
    with pytest.raises(ValidationError):
        ParcelCoreRecord(
            parcel_record_id="parcel:test",
            source_key="test:source",
            apn="123-456-78",
            normalized_apn="bad",
            county="Riverside",
        )


def test_parcel_core_record_requires_matching_normalized_address() -> None:
    with pytest.raises(ValidationError):
        ParcelCoreRecord(
            parcel_record_id="parcel:test",
            source_key="test:source",
            apn="123-456-78",
            normalized_apn="12345678",
            county="Riverside",
            address="123 Main St",
            normalized_address="bad",
        )


def test_parcel_core_record_serializes_to_dict() -> None:
    record = ParcelCoreRecord(
        parcel_record_id="parcel:test",
        source_key="test:source",
        source_record_id="1",
        apn="12345678",
        normalized_apn="12345678",
        county="Riverside",
        address="123 MAIN ST",
        normalized_address="123 MAIN ST",
    )

    payload = record.to_dict()

    assert payload["parcel_record_id"] == "parcel:test"
    assert payload["normalized_apn"] == "12345678"
