import json

from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_geometry import normalize_parcel_geometry
from constructionsight.parcel_site_resolution import resolve_site_with_parcels
from constructionsight.parcel_topology import (
    ParcelContainmentMethod,
    evaluate_parcel_point_containment,
)
from constructionsight.site_resolution_models import (
    GeometryHint,
    GeometryHintKind,
    SiteResolutionInput,
)


def _geometry(payload: dict[str, object], spatial_reference: str | None = "EPSG:4326"):
    return normalize_parcel_geometry(
        raw_geometry=json.dumps(payload),
        spatial_reference=spatial_reference,
    )


def _square_with_hole() -> dict[str, object]:
    return {
        "type": "Polygon",
        "coordinates": [
            [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]],
            [[1, 1], [3, 1], [3, 3], [1, 3], [1, 1]],
        ],
    }


def test_polygon_topology_matches_interior_point() -> None:
    geometry = _geometry(
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
        }
    )

    result = evaluate_parcel_point_containment(
        geometry,
        latitude=2,
        longitude=2,
    )

    assert result.contained is True
    assert result.method == ParcelContainmentMethod.POLYGON_TOPOLOGY
    assert result.reason == "coordinate hint falls within parcel polygon topology"
    assert result.limitations == ()


def test_concave_polygon_rejects_envelope_false_positive() -> None:
    geometry = _geometry(
        {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [4, 0], [4, 1], [1, 1], [1, 4], [0, 4], [0, 0]]
            ],
        }
    )

    result = evaluate_parcel_point_containment(
        geometry,
        latitude=3,
        longitude=3,
    )

    assert result.contained is False
    assert result.method == ParcelContainmentMethod.POLYGON_TOPOLOGY


def test_polygon_hole_excludes_interior_but_covers_boundary() -> None:
    geometry = _geometry(_square_with_hole())

    inside_hole = evaluate_parcel_point_containment(
        geometry,
        latitude=2,
        longitude=2,
    )
    on_hole_boundary = evaluate_parcel_point_containment(
        geometry,
        latitude=2,
        longitude=1,
    )

    assert inside_hole.contained is False
    assert on_hole_boundary.contained is True


def test_multipolygon_matches_point_in_second_polygon() -> None:
    geometry = _geometry(
        {
            "type": "MultiPolygon",
            "coordinates": [
                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                [[[3, 3], [4, 3], [4, 4], [3, 4], [3, 3]]],
            ],
        }
    )

    result = evaluate_parcel_point_containment(
        geometry,
        latitude=3.5,
        longitude=3.5,
    )

    assert result.contained is True
    assert result.method == ParcelContainmentMethod.POLYGON_TOPOLOGY


def test_unverified_spatial_reference_uses_limited_envelope_fallback() -> None:
    geometry = _geometry(
        {
            "type": "Polygon",
            "coordinates": [[[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]],
        },
        spatial_reference=None,
    )

    result = evaluate_parcel_point_containment(
        geometry,
        latitude=2,
        longitude=2,
    )

    assert result.contained is True
    assert result.method == ParcelContainmentMethod.ENVELOPE_FALLBACK
    assert "coordinate containment uses parcel envelope only" in result.limitations
    assert (
        "polygon topology was not used because the spatial reference is not verified "
        "as longitude/latitude"
    ) in result.limitations


def test_site_resolution_uses_topology_and_rejects_envelope_only_match() -> None:
    geometry = _geometry(
        {
            "type": "Polygon",
            "coordinates": [
                [[0, 0], [4, 0], [4, 1], [1, 1], [1, 4], [0, 4], [0, 0]]
            ],
        }
    )
    parcel = ParcelCoreRecord(
        parcel_record_id="parcel:topology",
        source_key="test:source",
        source_record_id="topology",
        apn="12345678",
        normalized_apn="12345678",
        county="Riverside",
        geometry=geometry,
    )
    outside_polygon = SiteResolutionInput(
        source_name="test source",
        geometry_hints=[
            GeometryHint(
                geometry_kind=GeometryHintKind.POINT,
                latitude=3,
                longitude=3,
                source_name="test source",
            )
        ],
    )
    inside_polygon = SiteResolutionInput(
        source_name="test source",
        geometry_hints=[
            GeometryHint(
                geometry_kind=GeometryHintKind.POINT,
                latitude=0.5,
                longitude=0.5,
                source_name="test source",
            )
        ],
    )

    rejected = resolve_site_with_parcels(outside_polygon, [parcel])
    matched = resolve_site_with_parcels(inside_polygon, [parcel])

    assert "no parcel core record matched site signals" in rejected.limitations
    assert matched.candidates[0].apn == "12345678"
    assert "coordinate hint falls within parcel polygon topology" in (
        matched.candidates[0].reasons
    )
    assert "coordinate containment uses parcel envelope only" not in (
        matched.candidates[0].limitations
    )
