from constructionsight.parcel_geometry import normalize_parcel_geometry
from constructionsight.parcel_topology import (
    ParcelContainmentMethod,
    evaluate_parcel_point_containment,
)


def test_wkt_polygon_topology_matches_interior_and_rejects_hole() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry=("POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0), (1 1, 3 1, 3 3, 1 3, 1 1))"),
        spatial_reference="EPSG:4326",
    )

    interior = evaluate_parcel_point_containment(
        geometry,
        latitude=0.5,
        longitude=0.5,
    )
    hole = evaluate_parcel_point_containment(
        geometry,
        latitude=2,
        longitude=2,
    )

    assert interior.contained is True
    assert interior.method == ParcelContainmentMethod.POLYGON_TOPOLOGY
    assert hole.contained is False
    assert hole.method == ParcelContainmentMethod.POLYGON_TOPOLOGY


def test_ewkt_multipolygon_topology_uses_embedded_srid() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry=(
            "SRID=4326;MULTIPOLYGON (((0 0, 1 0, 1 1, 0 1, 0 0)), ((3 3, 4 3, 4 4, 3 4, 3 3)))"
        ),
    )

    result = evaluate_parcel_point_containment(
        geometry,
        latitude=3.5,
        longitude=3.5,
    )

    assert geometry.spatial_reference == "EPSG:4326"
    assert result.contained is True
    assert result.method == ParcelContainmentMethod.POLYGON_TOPOLOGY


def test_explicit_projected_crs_is_not_compared_to_latlon_hint() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry="SRID=3857;POLYGON ((0 0, 4 0, 4 4, 0 4, 0 0))",
    )

    result = evaluate_parcel_point_containment(
        geometry,
        latitude=2,
        longitude=2,
    )

    assert result.contained is False
    assert result.method == ParcelContainmentMethod.NONE
    assert result.limitations == (
        "coordinate containment was not evaluated because the explicit spatial "
        "reference is not recognized as longitude/latitude",
    )


def test_wkt_z_coordinates_ignore_height_for_planar_topology() -> None:
    geometry = normalize_parcel_geometry(
        raw_geometry=("POLYGON Z ((0 0 10, 4 0 11, 4 4 12, 0 4 13, 0 0 10))"),
        spatial_reference="EPSG:4326",
    )

    result = evaluate_parcel_point_containment(
        geometry,
        latitude=2,
        longitude=2,
    )

    assert result.contained is True
    assert geometry.centroid_latitude == 2.0
    assert geometry.centroid_longitude == 2.0
