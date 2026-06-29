"""Parcel geometry normalization helpers."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from constructionsight.parcel_core_models import ParcelGeometry, ParcelGeometryKind

_WKT_POINT_RE = re.compile(
    r"POINT\s*\(\s*(?P<lon>-?\d+(?:\.\d+)?)\s+(?P<lat>-?\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)


def normalize_parcel_geometry(
    *,
    raw_geometry: str | None,
    geometry_kind: ParcelGeometryKind = ParcelGeometryKind.UNKNOWN,
    centroid_latitude: float | None = None,
    centroid_longitude: float | None = None,
    spatial_reference: str | None = None,
) -> ParcelGeometry:
    """Normalize raw geometry or centroid coordinates into a parcel geometry summary."""

    limitations: list[str] = []
    parsed_kind = geometry_kind
    calculated_centroid = (centroid_latitude, centroid_longitude)
    envelope: tuple[float | None, float | None, float | None, float | None] = (
        None,
        None,
        None,
        None,
    )

    if raw_geometry:
        parsed = _parse_raw_geometry(raw_geometry)
        if parsed is not None:
            parsed_kind, calculated_centroid, envelope = parsed
        else:
            limitations.append("raw geometry could not be parsed for envelope")
    if spatial_reference is None:
        limitations.append("spatial reference has not been verified")

    return ParcelGeometry(
        geometry_kind=parsed_kind,
        raw_geometry=raw_geometry,
        geometry_hash=_geometry_hash(raw_geometry) if raw_geometry else None,
        centroid_latitude=calculated_centroid[0],
        centroid_longitude=calculated_centroid[1],
        envelope_min_latitude=envelope[0],
        envelope_min_longitude=envelope[1],
        envelope_max_latitude=envelope[2],
        envelope_max_longitude=envelope[3],
        spatial_reference=spatial_reference,
        limitations=_unique(limitations),
    )


def _parse_raw_geometry(
    raw_geometry: str,
) -> tuple[
    ParcelGeometryKind,
    tuple[float | None, float | None],
    tuple[float | None, float | None, float | None, float | None],
] | None:
    """Parse supported raw geometry forms."""

    point_match = _WKT_POINT_RE.fullmatch(raw_geometry.strip())
    if point_match is not None:
        latitude = float(point_match.group("lat"))
        longitude = float(point_match.group("lon"))
        return (
            ParcelGeometryKind.POINT,
            (latitude, longitude),
            (latitude, longitude, latitude, longitude),
        )

    try:
        payload = json.loads(raw_geometry)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    geometry_type = str(payload.get("type") or "").lower()
    coordinates = payload.get("coordinates")
    points = _extract_points(coordinates)
    if not points:
        return None
    envelope = _envelope(points)
    centroid = _centroid(points)
    kind = _kind_from_geojson_type(geometry_type)
    return (kind, centroid, envelope)


def _extract_points(value: object) -> list[tuple[float, float]]:
    """Extract lon/lat coordinate pairs from GeoJSON-like nested coordinates."""

    if not isinstance(value, list):
        return []
    if len(value) >= 2 and all(isinstance(item, int | float) for item in value[:2]):
        longitude = float(value[0])
        latitude = float(value[1])
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return [(latitude, longitude)]
        return []
    points: list[tuple[float, float]] = []
    for item in value:
        points.extend(_extract_points(item))
    return points


def _kind_from_geojson_type(value: str) -> ParcelGeometryKind:
    """Convert GeoJSON type to canonical geometry kind."""

    if value == "point":
        return ParcelGeometryKind.POINT
    if value == "polygon":
        return ParcelGeometryKind.POLYGON
    if value == "multipolygon":
        return ParcelGeometryKind.MULTIPOLYGON
    return ParcelGeometryKind.UNKNOWN


def _centroid(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Return a simple coordinate-average centroid."""

    latitude = sum(point[0] for point in points) / len(points)
    longitude = sum(point[1] for point in points) / len(points)
    return (latitude, longitude)


def _envelope(
    points: list[tuple[float, float]],
) -> tuple[float, float, float, float]:
    """Return min/max latitude and longitude envelope."""

    latitudes = [point[0] for point in points]
    longitudes = [point[1] for point in points]
    return (min(latitudes), min(longitudes), max(latitudes), max(longitudes))


def _geometry_hash(raw_geometry: str) -> str:
    """Return deterministic geometry hash."""

    return hashlib.sha256(raw_geometry.encode("utf-8")).hexdigest()[:16]


def _unique(values: list[str]) -> list[str]:
    """Return values with duplicates removed in first-seen order."""

    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
