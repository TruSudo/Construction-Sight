"""Shared parcel topology parsing and planar summary calculations."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

from constructionsight.parcel_core_models import ParcelGeometryKind

Coordinate = tuple[float, float]
Ring = tuple[Coordinate, ...]
PolygonTopology = tuple[Ring, ...]
MultiPolygonTopology = tuple[PolygonTopology, ...]

_NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_WKT_HEADER_RE = re.compile(
    r"^\s*(?:SRID\s*=\s*(?P<srid>\d+)\s*;\s*)?"
    r"(?P<kind>POLYGON|MULTIPOLYGON)\s*(?:ZM|Z|M)?\s*(?P<body>\(.*\))\s*$",
    re.IGNORECASE | re.DOTALL,
)
_WKT_TOKEN_RE = re.compile(rf"\s*(?:(?P<number>{_NUMBER_PATTERN})|(?P<symbol>[(),]))")


@dataclass(frozen=True)
class ParsedParcelTopology:
    """Parsed polygon topology with source format and optional embedded CRS."""

    geometry_kind: ParcelGeometryKind
    polygons: MultiPolygonTopology
    source_format: str
    embedded_spatial_reference: str | None = None


@dataclass(frozen=True)
class TopologySummary:
    """Planar envelope, area-weighted centroid, and effective area summary."""

    centroid_latitude: float
    centroid_longitude: float
    envelope_min_latitude: float
    envelope_min_longitude: float
    envelope_max_latitude: float
    envelope_max_longitude: float
    effective_area: float


def parse_parcel_topology(raw_geometry: str | None) -> ParsedParcelTopology | None:
    """Parse supported GeoJSON or WKT Polygon/MultiPolygon topology."""

    if raw_geometry is None:
        return None
    geojson = _parse_geojson_topology(raw_geometry)
    if geojson is not None:
        return geojson
    return _parse_wkt_topology(raw_geometry)


def topology_fits_longitude_latitude(topology: MultiPolygonTopology) -> bool:
    """Return whether every topology vertex lies within longitude/latitude bounds."""

    return all(
        -180 <= longitude <= 180 and -90 <= latitude <= 90
        for polygon in topology
        for ring in polygon
        for longitude, latitude in ring
    )


def summarize_parcel_topology(
    topology: MultiPolygonTopology,
) -> TopologySummary | None:
    """Return planar area-weighted centroid and envelope for valid ring topology."""

    polygon_summaries: list[tuple[float, float, float]] = []
    all_points: list[Coordinate] = []
    for polygon in topology:
        polygon_summary = _summarize_polygon(polygon)
        if polygon_summary is None:
            return None
        polygon_summaries.append(polygon_summary)
        for ring in polygon:
            all_points.extend(ring)
    if not all_points:
        return None
    total_area = sum(summary[0] for summary in polygon_summaries)
    if total_area <= 1e-15:
        return None
    centroid_longitude = (
        sum(area * longitude for area, longitude, _latitude in polygon_summaries)
        / total_area
    )
    centroid_latitude = (
        sum(area * latitude for area, _longitude, latitude in polygon_summaries)
        / total_area
    )
    longitudes = [point[0] for point in all_points]
    latitudes = [point[1] for point in all_points]
    return TopologySummary(
        centroid_latitude=centroid_latitude,
        centroid_longitude=centroid_longitude,
        envelope_min_latitude=min(latitudes),
        envelope_min_longitude=min(longitudes),
        envelope_max_latitude=max(latitudes),
        envelope_max_longitude=max(longitudes),
        effective_area=total_area,
    )


def _parse_geojson_topology(raw_geometry: str) -> ParsedParcelTopology | None:
    """Parse GeoJSON Polygon or MultiPolygon rings while preserving holes."""

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
        polygon = _parse_geojson_polygon(coordinates)
        if polygon is None:
            return None
        return ParsedParcelTopology(
            geometry_kind=ParcelGeometryKind.POLYGON,
            polygons=(polygon,),
            source_format="geojson",
        )
    if geometry_type == "multipolygon":
        if not isinstance(coordinates, list):
            return None
        polygons: list[PolygonTopology] = []
        for value in coordinates:
            polygon = _parse_geojson_polygon(value)
            if polygon is None:
                return None
            polygons.append(polygon)
        if not polygons:
            return None
        return ParsedParcelTopology(
            geometry_kind=ParcelGeometryKind.MULTIPOLYGON,
            polygons=tuple(polygons),
            source_format="geojson",
        )
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


def _parse_geojson_polygon(value: object) -> PolygonTopology | None:
    """Parse one GeoJSON polygon into exterior and interior rings."""

    if not isinstance(value, list) or not value:
        return None
    rings: list[Ring] = []
    for ring_value in value:
        ring = _parse_geojson_ring(ring_value)
        if ring is None:
            return None
        rings.append(ring)
    return tuple(rings)


def _parse_geojson_ring(value: object) -> Ring | None:
    """Parse and normalize one GeoJSON ring."""

    if not isinstance(value, list):
        return None
    coordinates: list[Coordinate] = []
    for point_value in value:
        point = _parse_geojson_coordinate(point_value)
        if point is None:
            return None
        coordinates.append(point)
    return _normalize_ring(coordinates)


def _parse_geojson_coordinate(value: object) -> Coordinate | None:
    """Parse one finite GeoJSON coordinate pair without assuming its CRS."""

    if not isinstance(value, list) or len(value) < 2:
        return None
    raw_x = value[0]
    raw_y = value[1]
    if isinstance(raw_x, bool) or isinstance(raw_y, bool):
        return None
    if not isinstance(raw_x, int | float) or not isinstance(raw_y, int | float):
        return None
    return _finite_coordinate(float(raw_x), float(raw_y))


def _parse_wkt_topology(raw_geometry: str) -> ParsedParcelTopology | None:
    """Parse WKT/EWKT Polygon or MultiPolygon topology."""

    match = _WKT_HEADER_RE.fullmatch(raw_geometry)
    if match is None:
        return None
    tokens = _tokenize_wkt(match.group("body"))
    if tokens is None:
        return None
    parser = _WktParser(tokens)
    kind = match.group("kind").upper()
    polygons = (
        parser.parse_polygon_body()
        if kind == "POLYGON"
        else parser.parse_multipolygon_body()
    )
    if polygons is None or not parser.at_end:
        return None
    srid = match.group("srid")
    return ParsedParcelTopology(
        geometry_kind=(
            ParcelGeometryKind.POLYGON
            if kind == "POLYGON"
            else ParcelGeometryKind.MULTIPOLYGON
        ),
        polygons=polygons,
        source_format="wkt",
        embedded_spatial_reference=f"EPSG:{srid}" if srid is not None else None,
    )


def _tokenize_wkt(body: str) -> tuple[str, ...] | None:
    """Tokenize WKT coordinates and punctuation without accepting stray text."""

    tokens: list[str] = []
    position = 0
    while position < len(body):
        match = _WKT_TOKEN_RE.match(body, position)
        if match is None:
            return None
        token = match.group("number") or match.group("symbol")
        if token is None:
            return None
        tokens.append(token)
        position = match.end()
    return tuple(tokens)


class _WktParser:
    """Small deterministic parser for WKT polygon nesting."""

    def __init__(self, tokens: tuple[str, ...]) -> None:
        self._tokens = tokens
        self._index = 0

    @property
    def at_end(self) -> bool:
        return self._index == len(self._tokens)

    def parse_polygon_body(self) -> MultiPolygonTopology | None:
        polygon = self._parse_polygon_group()
        return (polygon,) if polygon is not None else None

    def parse_multipolygon_body(self) -> MultiPolygonTopology | None:
        if not self._consume("("):
            return None
        polygons: list[PolygonTopology] = []
        while True:
            polygon = self._parse_polygon_group()
            if polygon is None:
                return None
            polygons.append(polygon)
            if self._consume(")"):
                break
            if not self._consume(","):
                return None
        return tuple(polygons) if polygons else None

    def _parse_polygon_group(self) -> PolygonTopology | None:
        if not self._consume("("):
            return None
        rings: list[Ring] = []
        while True:
            ring = self._parse_ring_group()
            if ring is None:
                return None
            rings.append(ring)
            if self._consume(")"):
                break
            if not self._consume(","):
                return None
        return tuple(rings) if rings else None

    def _parse_ring_group(self) -> Ring | None:
        if not self._consume("("):
            return None
        coordinates: list[Coordinate] = []
        while True:
            coordinate = self._parse_coordinate()
            if coordinate is None:
                return None
            coordinates.append(coordinate)
            if self._consume(")"):
                break
            if not self._consume(","):
                return None
        return _normalize_ring(coordinates)

    def _parse_coordinate(self) -> Coordinate | None:
        x_token = self._consume_number()
        y_token = self._consume_number()
        if x_token is None or y_token is None:
            return None
        while self._peek_number():
            self._index += 1
        return _finite_coordinate(float(x_token), float(y_token))

    def _consume(self, expected: str) -> bool:
        if self._index >= len(self._tokens) or self._tokens[self._index] != expected:
            return False
        self._index += 1
        return True

    def _consume_number(self) -> str | None:
        if not self._peek_number():
            return None
        token = self._tokens[self._index]
        self._index += 1
        return token

    def _peek_number(self) -> bool:
        if self._index >= len(self._tokens):
            return False
        return self._tokens[self._index] not in {"(", ")", ","}


def _finite_coordinate(x_value: float, y_value: float) -> Coordinate | None:
    """Return a finite coordinate pair without assigning coordinate semantics."""

    if not math.isfinite(x_value) or not math.isfinite(y_value):
        return None
    return (x_value, y_value)


def _normalize_ring(coordinates: list[Coordinate]) -> Ring | None:
    """Remove a closing duplicate and require three distinct vertices."""

    if len(coordinates) > 1 and _coordinates_equal(coordinates[0], coordinates[-1]):
        coordinates.pop()
    if len(coordinates) < 3 or len(set(coordinates)) < 3:
        return None
    return tuple(coordinates)


def _summarize_polygon(
    polygon: PolygonTopology,
) -> tuple[float, float, float] | None:
    """Return effective area and centroid after subtracting interior holes."""

    exterior = _summarize_ring(polygon[0])
    if exterior is None:
        return None
    exterior_area, exterior_x, exterior_y = exterior
    effective_area = exterior_area
    weighted_x = exterior_area * exterior_x
    weighted_y = exterior_area * exterior_y
    for hole in polygon[1:]:
        hole_summary = _summarize_ring(hole)
        if hole_summary is None:
            return None
        hole_area, hole_x, hole_y = hole_summary
        effective_area -= hole_area
        weighted_x -= hole_area * hole_x
        weighted_y -= hole_area * hole_y
    if effective_area <= 1e-15:
        return None
    return (
        effective_area,
        weighted_x / effective_area,
        weighted_y / effective_area,
    )


def _summarize_ring(ring: Ring) -> tuple[float, float, float] | None:
    """Return absolute planar area and orientation-independent ring centroid."""

    twice_signed_area = 0.0
    x_numerator = 0.0
    y_numerator = 0.0
    previous = ring[-1]
    for current in ring:
        cross = previous[0] * current[1] - current[0] * previous[1]
        twice_signed_area += cross
        x_numerator += (previous[0] + current[0]) * cross
        y_numerator += (previous[1] + current[1]) * cross
        previous = current
    if abs(twice_signed_area) <= 1e-15:
        return None
    centroid_x = x_numerator / (3.0 * twice_signed_area)
    centroid_y = y_numerator / (3.0 * twice_signed_area)
    return (abs(twice_signed_area) / 2.0, centroid_x, centroid_y)


def _coordinates_equal(first: Coordinate, second: Coordinate) -> bool:
    """Return whether two coordinates are equal within numeric tolerance."""

    return abs(first[0] - second[0]) <= 1e-10 and abs(first[1] - second[1]) <= 1e-10
