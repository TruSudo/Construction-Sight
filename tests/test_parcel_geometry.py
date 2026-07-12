import json

import pytest

from constructionsight.parcel_core_models import ParcelGeometryKind
from constructionsight.parcel_geometry import normalize_parcel_geometry

_PLANAR_CENTROID_LIMITATION = (
    "polygon centroid is area-weighted in the source coordinate plane, not projection-aware"
)


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
    assert geometry.centroid_latitude == pytest.approx(34.05)
    assert geometry.centroid_longitude == pytest.approx(-117.05)
    assert geometry.limitations == [_PLANAR_CENTROID_LIMITATION]


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


def test_normalize_wkt_polygon_area_weighted_centroid() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry="POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0))",
        spatial_reference="EPSG:4326",
    )

    assert geometry.geometry_kind == ParcelGeometryKind.POLYGON
    assert geometry.centroid_latitude == pytest.approx(2.0)
    assert geometry.centroid_longitude == pytest.approx(2.0)
    assert geometry.envelope_min_latitude == 0.0
    assert geometry.envelope_max_longitude == 4.0
    assert geometry.limitations == [_PLANAR_CENTROID_LIMITATION]


def test_normalize_wkt_polygon_subtracts_hole_area() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry=(
            "POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0), "
            "(0.5 0.5, 1.5 0.5, 1.5 1.5, 0.5 1.5, 0.5 0.5))"
        ),
        spatial_reference="EPSG:4326",
    )

    assert geometry.centroid_latitude == pytest.approx(31 / 15)
    assert geometry.centroid_longitude == pytest.approx(31 / 15)


def test_normalize_ewkt_multipolygon_uses_embedded_srid() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry=(
            "SRID=4326;MULTIPOLYGON (((0 0, 2 0, 2 2, 0 2, 0 0)), "
            "((4 0, 6 0, 6 2, 4 2, 4 0)))"
        ),
    )

    assert geometry.geometry_kind == ParcelGeometryKind.MULTIPOLYGON
    assert geometry.spatial_reference == "EPSG:4326"
    assert geometry.centroid_latitude == pytest.approx(1.0)
    assert geometry.centroid_longitude == pytest.approx(3.0)
    assert "spatial reference has not been verified" not in geometry.limitations


def test_explicit_projected_crs_preserves_raw_geometry_without_latlon_summary() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry="SRID=3857;POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0))",
    )

    assert geometry.geometry_kind == ParcelGeometryKind.POLYGON
    assert geometry.spatial_reference == "EPSG:3857"
    assert geometry.centroid_latitude is None
    assert geometry.centroid_longitude is None
    assert geometry.envelope_min_latitude is None
    assert geometry.envelope_min_longitude is None
    assert (
        "geometry coordinates were not summarized because the explicit spatial "
        "reference is not recognized as longitude/latitude"
    ) in geometry.limitations


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
