"""Topology-aware parcel point containment without external geometry dependencies."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from constructionsight.parcel_core_models import ParcelGeometry, ParcelGeometryKind

Coordinate = tuple[float, float]
Ring = tuple[Coordinate, ...]
PolygonTopology = tuple[Ring, ...]
MultiPolygonTopology = tuple[PolygonTopology, ...]

_ENVELOPE_LIMITATION = "coordinate containment uses parcel envelope only"
_UNVERIFIED_CRS_LIMITATION = (
    "polygon topology was not used because the spatial reference is not verified "
    "as longitude/latitude"
)
_UNPARSEABLE_TOPOLOGY_LIMITATION = (
    "polygon topology was not used because raw geometry could not be parsed as GeoJSON"
)
_MISSING_TOPOLOGY_LIMITATION = (
    "polygon topology was not used because raw polygon geometry is unavailable"
)


class ParcelContainmentMethod(StrEnum):
    """Method used to evaluate a coordinate against parcel geometry."""

    POINT = "point"
    POLYGON_TOPOLOGY = "polygon_topology"
    ENVELOPE_FALLBACK = "envelope_fallback"
    NONE = "none"


@dataclass(frozen=True)
class ParcelPointContainment:
    """Result of evaluating one point against one parcel geometry."""

    contained: bool
    method: ParcelContainmentMethod
    reason: str | None = None
    limitations: tuple[str, ...] = ()


def evaluate_parcel_point_containment(
    geometry: ParcelGeometry,
    *,
    latitude: float,
    longitude: float,
) -> ParcelPointContainment:
    """Evaluate one WGS84-style point with topology when the geometry supports it."""

    if geometry.geometry_kind == ParcelGeometryKind.POINT:
        return _point_geometry_containment(
            geometry,
            latitude=latitude,
            longitude=longitude,
        )
    if geometry.geometry_kind in {
        ParcelGeometryKind.POLYGON,
        ParcelGeometryKind.MULTIPOLYGON,
    }:
        topology = _parse_geojson_topology(geometry.raw_geometry)
        if topology is not None and _is_verified_longitude_latitude(
            geometry.spatial_reference
        ):
            contained = _point_in_multipolygon(
                longitude=longitude,
                latitude=latitude,
                topology=topology,
            )
            return ParcelPointContainment(
                contained=contained,
                method=ParcelContainmentMethod.POLYGON_TOPOLOGY,
                reason=(
                    "coordinate hint falls within parcel polygon topology"
                    if contained
                    else None
                ),
            )
        fallback_limitations: list[str] = [_ENVELOPE_LIMITATION]
        if topology is None:
            fallback_limitations.append(
                _MISSING_TOPOLOGY_LIMITATION
                if geometry.raw_geometry is None
                else _UNPARSEABLE_TOPOLOGY_LIMITATION
            )
        if not _is_verified_longitude_latitude(geometry.spatial_reference):
            fallback_limitations.append(_UNVERIFIED_CRS_LIMITATION)
        return _envelope_containment(
            geometry,
            latitude=latitude,
            longitude=longitude,
            limitations=tuple(dict.fromkeys(fallback_limitations)),
        )
    return _envelope_containment(
        geometry,
        latitude=latitude,
        longitude=longitude,
        limitations=(_ENVELOPE_LIMITATION,),
    )


def _point_geometry_containment(
    geometry: ParcelGeometry,
    *,
    latitude: float,
    longitude: float,
) -> ParcelPointContainment:
    """Match a point geometry by its normalized centroid coordinate."""

    if geometry.centroid_latitude is None or geometry.centroid_longitude is None:
        return _envelope_containment(
            geometry,
            latitude=latitude,
            longitude=longitude,
            limitations=(_ENVELOPE_LIMITATION,),
        )
    contained = _coordinates_equal(
        first=(longitude, latitude),
        second=(geometry.centroid_longitude, geometry.centroid_latitude),
    )
    return ParcelPointContainment(
        contained=contained,
        method=ParcelContainmentMethod.POINT,
        reason="coordinate hint matches parcel point geometry" if contained else None,
    )


def _envelope_containment(
    geometry: ParcelGeometry,
    *,
    latitude: float,
    longitude: float,
    limitations: tuple[str, ...],
) -> ParcelPointContainment:
    """Evaluate the geometry envelope as a conservative fallback."""

    bounds = (
        geometry.envelope_min_latitude,
        geometry.envelope_min_longitude,
        geometry.envelope_max_latitude,
        geometry.envelope_max_longitude,
    )
    if any(value is None for value in bounds):
        return ParcelPointContainment(
            contained=False,
            method=ParcelContainmentMethod.NONE,
            limitations=limitations,
        )
    min_latitude, min_longitude, max_latitude, max_longitude = bounds
    assert min_latitude is not None
    assert min_longitude is not None
    assert max_latitude is not None
    assert max_longitude is not None
    contained = (
        min_latitude <= latitude <= max_latitude
        and min_longitude <= longitude <= max_longitude
    )
    return ParcelPointContainment(
        contained=contained,
        method=ParcelContainmentMethod.ENVELOPE_FALLBACK,
        reason="coordinate hint falls within parcel envelope" if contained else None,
        limitations=limitations,
    )


def _parse_geojson_topology(raw_geometry: str | None) -> MultiPolygonTopology | None:
    """Parse GeoJSON Polygon or MultiPolygon rings while preserving holes."""

    if raw_geometry is None:
        return None
    try:
        payload = json.loads(raw_geometry)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    geometry = _geojson_geometry_payload(payload)
    if geometry is None:
        return None
    geometry_type = str(geometry.get("type") or "").lower()
    coordinates = geometry.get("coordinates")
    if geometry_type == "polygon":
        polygon = _parse_polygon(coordinates)
        return (polygon,) if polygon is not None else None
    if geometry_type == "multipolygon":
        if not isinstance(coordinates, list):
            return None
        polygons: list[PolygonTopology] = []
        for value in coordinates:
            polygon = _parse_polygon(value)
            if polygon is None:
                return None
            polygons.append(polygon)
        return tuple(polygons) if polygons else None
    return None


def _geojson_geometry_payload(payload: dict[str, object]) -> dict[str, object] | None:
    """Return a GeoJSON geometry from geometry, Feature, or FeatureCollection input."""

    payload_type = str(payload.get("type") or "").lower()
    if payload_type == "feature":
        geometry = payload.get("geometry")
        return geometry if isinstance(geometry, dict) else None
    if payload_type == "featurecollection":
        features = payload.get("features")
        if not isinstance(features, list) or not features:
            return None
        first_feature = features[0]
        if not isinstance(first_feature, dict):
            return None
        geometry = first_feature.get("geometry")
        return geometry if isinstance(geometry, dict) else None
    return payload


def _parse_polygon(value: object) -> PolygonTopology | None:
    """Parse one GeoJSON polygon into exterior and interior rings."""

    if not isinstance(value, list) or not value:
        return None
    rings: list[Ring] = []
    for ring_value in value:
        ring = _parse_ring(ring_value)
        if ring is None:
            return None
        rings.append(ring)
    return tuple(rings)


def _parse_ring(value: object) -> Ring | None:
    """Parse and normalize one closed or open GeoJSON linear ring."""

    if not isinstance(value, list):
        return None
    coordinates: list[Coordinate] = []
    for point_value in value:
        point = _parse_coordinate(point_value)
        if point is None:
            return None
        coordinates.append(point)
    if len(coordinates) > 1 and _coordinates_equal(coordinates[0], coordinates[-1]):
        coordinates.pop()
    if len(coordinates) < 3 or len(set(coordinates)) < 3:
        return None
    return tuple(coordinates)


def _parse_coordinate(value: object) -> Coordinate | None:
    """Parse one GeoJSON longitude/latitude pair."""

    if not isinstance(value, list) or len(value) < 2:
        return None
    raw_longitude = value[0]
    raw_latitude = value[1]
    if isinstance(raw_longitude, bool) or isinstance(raw_latitude, bool):
        return None
    if not isinstance(raw_longitude, int | float) or not isinstance(
        raw_latitude, int | float
    ):
        return None
    longitude = float(raw_longitude)
    latitude = float(raw_latitude)
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        return None
    return (longitude, latitude)


def _point_in_multipolygon(
    *,
    longitude: float,
    latitude: float,
    topology: MultiPolygonTopology,
) -> bool:
    """Return whether a point is covered by any polygon in a multipolygon."""

    point = (longitude, latitude)
    return any(_point_in_polygon(point, polygon) for polygon in topology)


def _point_in_polygon(point: Coordinate, polygon: PolygonTopology) -> bool:
    """Return whether a point is covered by a polygon exterior minus its holes."""

    exterior = polygon[0]
    if _point_on_ring_boundary(point, exterior):
        return True
    if not _point_in_ring(point, exterior):
        return False
    for hole in polygon[1:]:
        if _point_on_ring_boundary(point, hole):
            return True
        if _point_in_ring(point, hole):
            return False
    return True


def _point_in_ring(point: Coordinate, ring: Ring) -> bool:
    """Return whether a non-boundary point is inside one ring by ray casting."""

    longitude, latitude = point
    inside = False
    previous = ring[-1]
    for current in ring:
        current_longitude, current_latitude = current
        previous_longitude, previous_latitude = previous
        crosses_latitude = (current_latitude > latitude) != (
            previous_latitude > latitude
        )
        if crosses_latitude:
            intersection_longitude = (
                (previous_longitude - current_longitude)
                * (latitude - current_latitude)
                / (previous_latitude - current_latitude)
                + current_longitude
            )
            if longitude < intersection_longitude:
                inside = not inside
        previous = current
    return inside


def _point_on_ring_boundary(point: Coordinate, ring: Ring) -> bool:
    """Return whether a point lies on any ring segment."""

    previous = ring[-1]
    for current in ring:
        if _point_on_segment(point, previous, current):
            return True
        previous = current
    return False


def _point_on_segment(
    point: Coordinate,
    start: Coordinate,
    end: Coordinate,
) -> bool:
    """Return whether a point lies on a line segment within numeric tolerance."""

    longitude, latitude = point
    start_longitude, start_latitude = start
    end_longitude, end_latitude = end
    cross_product = (
        (longitude - start_longitude) * (end_latitude - start_latitude)
        - (latitude - start_latitude) * (end_longitude - start_longitude)
    )
    if abs(cross_product) > 1e-10:
        return False
    return (
        min(start_longitude, end_longitude) - 1e-10
        <= longitude
        <= max(start_longitude, end_longitude) + 1e-10
        and min(start_latitude, end_latitude) - 1e-10
        <= latitude
        <= max(start_latitude, end_latitude) + 1e-10
    )


def _coordinates_equal(first: Coordinate, second: Coordinate) -> bool:
    """Return whether two coordinates are equal within numeric tolerance."""

    return abs(first[0] - second[0]) <= 1e-10 and abs(first[1] - second[1]) <= 1e-10


def _is_verified_longitude_latitude(spatial_reference: str | None) -> bool:
    """Return whether the CRS is explicitly recognized as longitude/latitude."""

    if spatial_reference is None:
        return False
    normalized = spatial_reference.strip().upper().replace(" ", "")
    return normalized in {
        "EPSG:4326",
        "CRS84",
        "OGC:CRS84",
        "URN:OGC:DEF:CRS:OGC::CRS84",
    }
