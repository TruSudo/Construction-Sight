import json

from constructionsight.parcel_core_models import ParcelGeometryKind
from constructionsight.parcel_geometry import normalize_parcel_geometry


def test_normalize_wkt_point_geometry() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry="POINT (-117.2 34.1)",
        spatial_reference="EPSG:4326",
    )

    assert geometry.geometry_kind == ParcelGeometryKind.POINT
    assert geometry.centroid_latitude == 34.1
    assert geometry.centroid_longitude == -117.2
    assert geometry.envelope_min_latitude == 34.1
    assert geometry.envelope_max_longitude == -117.2
    assert geometry.geometry_hash is not None
    assert geometry.limitations == []


def test_normalize_geojson_polygon_geometry() -> None:
    raw_geometry = json.dumps(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [-117.0, 34.0],
                    [-117.1, 34.0],
                    [-117.1, 34.1],
                    [-117.0, 34.1],
                    [-117.0, 34.0],
                ]
            ],
        }
    )

    geometry = normalize_parcel_geometry(
        raw_geometry=raw_geometry,
        spatial_reference="EPSG:4326",
    )

    assert geometry.geometry_kind == ParcelGeometryKind.POLYGON
    assert geometry.envelope_min_latitude == 34.0
    assert geometry.envelope_min_longitude == -117.1
    assert geometry.envelope_max_latitude == 34.1
    assert geometry.envelope_max_longitude == -117.0
    assert geometry.centroid_latitude == 34.05
    assert geometry.centroid_longitude == -117.05
    assert geometry.limitations == [
        "polygon centroid is a coordinate-average approximation, not an area-weighted centroid"
    ]


def test_normalize_geojson_feature_geometry() -> None:
    raw_geometry = json.dumps(
        {
            "type": "Feature",
            "properties": {"apn": "123"},
            "geometry": {"type": "Point", "coordinates": [-117.2, 34.1]},
        }
    )

    geometry = normalize_parcel_geometry(
        raw_geometry=raw_geometry,
        spatial_reference="EPSG:4326",
    )

    assert geometry.geometry_kind == ParcelGeometryKind.POINT
    assert geometry.centroid_latitude == 34.1
    assert geometry.centroid_longitude == -117.2


def test_unparseable_geometry_preserves_hash_and_limitation() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry="not geometry",
        geometry_kind=ParcelGeometryKind.UNKNOWN,
        spatial_reference=None,
    )

    assert geometry.geometry_kind == ParcelGeometryKind.UNKNOWN
    assert geometry.geometry_hash is not None
    assert "raw geometry could not be parsed for envelope" in geometry.limitations
    assert "spatial reference has not been verified" in geometry.limitations


def test_centroid_only_geometry() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry=None,
        geometry_kind=ParcelGeometryKind.POINT,
        centroid_latitude=34.1,
        centroid_longitude=-117.2,
        spatial_reference="EPSG:4326",
    )

    assert geometry.geometry_kind == ParcelGeometryKind.POINT
    assert geometry.centroid_latitude == 34.1
    assert geometry.centroid_longitude == -117.2
