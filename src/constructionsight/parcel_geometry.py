"""Parcel geometry normalization helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from constructionsight.parcel_core_models import ParcelGeometry, ParcelGeometryKind
from constructionsight.parcel_topology_parse import (
    Coordinate,
    ParsedParcelTopology,
    parse_parcel_topology,
    summarize_parcel_topology,
)

_NUMBER_PATTERN = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_WKT_POINT_RE = re.compile(
    rf"^\s*(?:SRID\s*=\s*(?P<srid>\d+)\s*;\s*)?POINT\s*(?:ZM|Z|M)?\s*"
    rf"\(\s*(?P<lon>{_NUMBER_PATTERN})\s+(?P<lat>{_NUMBER_PATTERN})"
    rf"(?:\s+{_NUMBER_PATTERN})*\s*\)\s*$",
    re.IGNORECASE,
)
_PLANAR_CENTROID_LIMITATION = (
    "polygon centroid is area-weighted in the source coordinate plane, not projection-aware"
)
_INVALID_AREA_LIMITATION = (
    "polygon centroid is unavailable because topology has zero or invalid effective area"
)
_INCOMPATIBLE_CRS_SUMMARY_LIMITATION = (
    "geometry coordinates were not summarized because the explicit spatial reference "
    "is not recognized as longitude/latitude"
)


@dataclass(frozen=True)
class _ParsedPoint:
    latitude: float
    longitude: float
    embedded_spatial_reference: str | None = None


def normalize_parcel_geometry(
    *,
    raw_geometry: str | None,
    geometry_kind: ParcelGeometryKind = ParcelGeometryKind.UNKNOWN,
    centroid_latitude: float | None = None,
    centroid_longitude: float | None = None,
    spatial_reference: str | None = None,
) -> ParcelGeometry:
    """Normalize raw geometry without silently crossing coordinate systems."""

    limitations: list[str] = []
    parsed_kind = geometry_kind
    calculated_centroid = (centroid_latitude, centroid_longitude)
    envelope: tuple[float | None, float | None, float | None, float | None] = (
        None,
        None,
        None,
        None,
    )
    effective_spatial_reference = spatial_reference

    if raw_geometry:
        parsed_point = _parse_point_geometry(raw_geometry)
        parsed_topology = parse_parcel_topology(raw_geometry)
        embedded_spatial_reference = _embedded_spatial_reference(
            parsed_point,
            parsed_topology,
        )
        if (
            spatial_reference is not None
            and embedded_spatial_reference is not None
            and not _same_spatial_reference(
                spatial_reference,
                embedded_spatial_reference,
            )
        ):
            limitations.append(
                "supplied spatial reference conflicts with the geometry-embedded "
                f"spatial reference {embedded_spatial_reference}"
            )
        effective_spatial_reference = spatial_reference or embedded_spatial_reference
        explicit_incompatible_crs = (
            effective_spatial_reference is not None
            and not _is_verified_longitude_latitude(effective_spatial_reference)
        )

        if parsed_point is not None:
            parsed_kind = ParcelGeometryKind.POINT
            if explicit_incompatible_crs:
                limitations.append(_INCOMPATIBLE_CRS_SUMMARY_LIMITATION)
            else:
                calculated_centroid = (
                    parsed_point.latitude,
                    parsed_point.longitude,
                )
                envelope = (
                    parsed_point.latitude,
                    parsed_point.longitude,
                    parsed_point.latitude,
                    parsed_point.longitude,
                )
        elif parsed_topology is not None:
            parsed_kind = parsed_topology.geometry_kind
            if explicit_incompatible_crs:
                limitations.append(_INCOMPATIBLE_CRS_SUMMARY_LIMITATION)
            else:
                envelope = _topology_envelope(parsed_topology)
                summary = summarize_parcel_topology(parsed_topology.polygons)
                if summary is None:
                    limitations.append(_INVALID_AREA_LIMITATION)
                else:
                    calculated_centroid = (
                        summary.centroid_latitude,
                        summary.centroid_longitude,
                    )
                    limitations.append(_PLANAR_CENTROID_LIMITATION)
        else:
            limitations.append("raw geometry could not be parsed for envelope")
    if effective_spatial_reference is None:
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
        spatial_reference=effective_spatial_reference,
        limitations=_unique(limitations),
    )


def _parse_point_geometry(raw_geometry: str) -> _ParsedPoint | None:
    """Parse supported WKT/EWKT or GeoJSON point geometry."""

    point_match = _WKT_POINT_RE.fullmatch(raw_geometry)
    if point_match is not None:
        longitude = float(point_match.group("lon"))
        latitude = float(point_match.group("lat"))
        if not _valid_longitude_latitude(longitude, latitude):
            return None
        srid = point_match.group("srid")
        return _ParsedPoint(
            latitude=latitude,
            longitude=longitude,
            embedded_spatial_reference=f"EPSG:{srid}" if srid is not None else None,
        )

    try:
        payload = json.loads(raw_geometry)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    geometry_payload = _geojson_geometry_payload(payload)
    if geometry_payload is None:
        return None
    if str(geometry_payload.get("type") or "").lower() != "point":
        return None
    coordinates = geometry_payload.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None
    raw_longitude = coordinates[0]
    raw_latitude = coordinates[1]
    if isinstance(raw_longitude, bool) or isinstance(raw_latitude, bool):
        return None
    if not isinstance(raw_longitude, int | float) or not isinstance(
        raw_latitude, int | float
    ):
        return None
    longitude = float(raw_longitude)
    latitude = float(raw_latitude)
    if not _valid_longitude_latitude(longitude, latitude):
        return None
    return _ParsedPoint(latitude=latitude, longitude=longitude)


def _geojson_geometry_payload(payload: dict[str, object]) -> dict[str, object] | None:
    """Return a GeoJSON geometry object from geometry, feature, or feature collection input."""

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


def _embedded_spatial_reference(
    parsed_point: _ParsedPoint | None,
    parsed_topology: ParsedParcelTopology | None,
) -> str | None:
    """Return the geometry-embedded spatial reference, when available."""

    if parsed_point is not None:
        return parsed_point.embedded_spatial_reference
    if parsed_topology is not None:
        return parsed_topology.embedded_spatial_reference
    return None


def _topology_envelope(
    parsed_topology: ParsedParcelTopology,
) -> tuple[float, float, float, float]:
    """Return a latitude/longitude envelope from parsed topology vertices."""

    points: list[Coordinate] = []
    for polygon in parsed_topology.polygons:
        for ring in polygon:
            points.extend(ring)
    latitudes = [point[1] for point in points]
    longitudes = [point[0] for point in points]
    return (min(latitudes), min(longitudes), max(latitudes), max(longitudes))


def _valid_longitude_latitude(longitude: float, latitude: float) -> bool:
    """Return whether a coordinate lies in geographic longitude/latitude bounds."""

    return -180 <= longitude <= 180 and -90 <= latitude <= 90


def _same_spatial_reference(first: str, second: str) -> bool:
    """Return whether two spatial-reference labels normalize identically."""

    return _normalized_spatial_reference(first) == _normalized_spatial_reference(second)


def _is_verified_longitude_latitude(spatial_reference: str) -> bool:
    """Return whether the CRS is explicitly recognized as longitude/latitude."""

    return _normalized_spatial_reference(spatial_reference) in {
        "EPSG:4326",
        "CRS84",
        "OGC:CRS84",
        "URN:OGC:DEF:CRS:OGC::CRS84",
    }


def _normalized_spatial_reference(value: str) -> str:
    """Normalize a spatial-reference label for conservative comparison."""

    return value.strip().upper().replace(" ", "")


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
