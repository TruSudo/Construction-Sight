"""Optional, hash-bound county assessment-use claims at reported site coordinates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx

from constructionsight.parcel_topology import _point_in_ring, _point_on_ring_boundary
from constructionsight.parcel_use_enrichment import (
    FIELDS,
    LAYER,
    eligible_for_parcel_type,
    source_use_type,
)


def coordinates(row: dict[str, Any]) -> tuple[float, float] | None:
    try:
        lon, lat = float(row["SITE_LONGITUDE"]), float(row["SITE_LATITUDE"])
    except (KeyError, TypeError, ValueError):
        return None
    return (
        (lon, lat)
        if math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90
        else None
    )


def containment(point: tuple[float, float], geometry: dict[str, Any]) -> bool | None:
    """Even/odd rings preserve holes; boundary or malformed rings are ambiguous."""
    rings = geometry.get("rings")
    if not isinstance(rings, list) or not rings:
        raise ValueError("Missing county parcel polygon")
    inside = False
    for raw in rings:
        if not isinstance(raw, list) or len(raw) < 4:
            raise ValueError("Invalid county parcel ring")
        ring = tuple(tuple(float(v) for v in pair) for pair in raw)
        if (
            any(len(pair) != 2 or not all(math.isfinite(v) for v in pair) for pair in ring)
            or ring[0] != ring[-1]
        ):
            raise ValueError("Invalid county parcel coordinates")
        points = tuple((pair[0], pair[1]) for pair in ring)
        if _point_on_ring_boundary(point, points):
            return None
        inside ^= _point_in_ring(point, points)
    return inside


def claims_from_responses(
    rows: list[dict[str, Any]], responses: list[dict[str, Any]], directory: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    by_key = {
        r["source_key"]: r
        for r in rows
        if eligible_for_parcel_type(r) and r.get("SITE_COUNTY") == "Riverside"
    }
    candidates: dict[str, list[dict[str, Any]]] = {}
    boundary: set[str] = set()
    for response in responses:
        url = urlsplit(response["source_url"])
        if url.scheme + "://" + url.netloc + url.path != LAYER + "/query":
            raise ValueError("Unreviewed spatial parcel source")
        query = parse_qs(url.query)
        if (
            query.get("outSR") != ["4326"]
            or query.get("inSR") != ["4326"]
            or query.get("geometryType") != ["esriGeometryPoint"]
        ):
            raise ValueError("Spatial parcel query must use a WGS84 point")
        geometry = json.loads(query["geometry"][0])
        requested = [[geometry["x"], geometry["y"]]]
        targets = response["targets"]
        if len(targets) != 1 or any(point not in requested for point in targets.values()):
            raise ValueError("Spatial targets do not match retained query")
        path = (directory / response["path"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Spatial response path escapes data folder")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != response["sha256"]:
            raise ValueError("Spatial parcel response hash mismatch")
        payload = json.loads(raw)
        if (
            payload.get("error")
            or payload.get("exceededTransferLimit")
            or payload.get("spatialReference", {}).get("wkid") != 4326
        ):
            raise ValueError("Spatial parcel response incomplete or incompatible")
        for key, point in targets.items():
            row = by_key.get(key)
            if row is None or coordinates(row) != tuple(point):
                continue
            candidates.setdefault(key, [])
            for feature in payload["features"]:
                result = containment(tuple(point), feature["geometry"])
                if result is None:
                    boundary.add(key)
                elif result:
                    candidates[key].append({**feature["attributes"], "response": response})
    claims = {}
    counts = {
        "eligible": len(candidates),
        "ambiguous": 0,
        "no_match": 0,
        "unmapped_use": 0,
        "classified": 0,
    }
    for key, matches in candidates.items():
        identities = {(str(m.get("APN") or ""), str(m.get("CLASS_CODE") or "")) for m in matches}
        if key in boundary or len(identities) > 1:
            counts["ambiguous"] += 1
            continue
        if not identities:
            counts["no_match"] += 1
            continue
        match = matches[0]
        classified = source_use_type(
            match.get("CLASS_CODE"), site_name=str(by_key[key].get("SITE_NAME") or "")
        )
        if not match.get("APN") or not classified:
            counts["unmapped_use"] += 1
            continue
        claims[key] = {
            **classified,
            "confidence": 0.45,
            "confidence_basis": (
                "Heuristic assessment-use signal at reported coordinates; approximate boundaries "
                "and current parcel use do not verify proposed project use"
            ),
            "match_method": "unique parcel interior at source-reported coordinates",
            "coordinates": list(coordinates(by_key[key]) or ()),
            "apn": match["APN"],
            "address": match.get("SITUS_STREET") or None,
            "city": match.get("SITUS_CITY") or None,
            "county": "Riverside",
            "source_url": match["response"]["source_url"],
            "response_sha256": match["response"]["sha256"],
            "captured_at": match["response"]["captured_at"],
        }
        counts["classified"] += 1
    return claims, counts


def load_claims(directory: Path, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    path = directory / "spatial-parcel-use.json"
    if not path.exists():
        return {}
    claims, _ = claims_from_responses(rows, json.loads(path.read_text())["responses"], directory)
    return claims


def collect(
    client: httpx.Client,
    rows: list[dict[str, Any]],
    directory: Path,
    *,
    max_leads: int = 250,
    max_seconds: int = 300,
) -> dict[str, Any]:
    if not 1 <= max_leads <= 2500 or not 1 <= max_seconds <= 600:
        raise ValueError("Spatial pass requires 1–2500 leads and 1–600 seconds")
    targets = [
        r
        for r in rows
        if eligible_for_parcel_type(r) and r.get("SITE_COUNTY") == "Riverside" and coordinates(r)
    ]
    (directory / "spatial-parcel-evidence").mkdir(parents=True, exist_ok=True, mode=0o700)
    existing = directory / "spatial-parcel-use.json"
    prior = json.loads(existing.read_text()) if existing.exists() else {}
    responses: list[dict[str, Any]] = prior.get("responses", [])
    claims_from_responses(rows, responses, directory)
    errors = prior.get("errors", [])
    attempted = {key for record in responses for key in record["targets"]}
    attempted.update(e["source_key"] for e in errors)
    pending = [r for r in targets if r["source_key"] not in attempted]
    started = time.monotonic()
    request_count = 0
    for row in pending[:max_leads]:
        if time.monotonic() - started >= max_seconds:
            break
        point = coordinates(row)
        assert point is not None
        request_count += 1
        try:
            response = client.get(
                LAYER + "/query",
                params={
                    "f": "json",
                    "geometry": json.dumps(
                        {"x": point[0], "y": point[1], "spatialReference": {"wkid": 4326}}
                    ),
                    "geometryType": "esriGeometryPoint",
                    "inSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects",
                    "outFields": FIELDS,
                    "returnGeometry": "true",
                    "outSR": 4326,
                    "resultRecordCount": 1000,
                },
            )
            response.raise_for_status()
            if len(response.content) > 4_000_000:
                raise ValueError("Spatial response exceeds bounded payload limit")
            payload = response.json()
            if payload.get("error") or payload.get("exceededTransferLimit"):
                errors.append(
                    {
                        "source_key": row["source_key"],
                        "error": "Incomplete or rejected parcel query; no claim",
                    }
                )
                continue
            digest = hashlib.sha256(response.content).hexdigest()
            relative = "spatial-parcel-evidence/" + digest + ".json"
            (directory / relative).write_bytes(response.content)
            record = {
                "source_url": str(response.url),
                "sha256": digest,
                "path": relative,
                "captured_at": datetime.now(UTC).isoformat(),
                "targets": {row["source_key"]: list(point)},
            }
            claims_from_responses([row], [record], directory)
            responses.append(record)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            errors.append({"source_key": row["source_key"], "error": str(exc)})
            break  # Includes 403: stop this source, no retries or alternate access.
    claims, counts = claims_from_responses(rows, responses, directory)
    result = {
        "responses": responses,
        "claims": claims,
        "counts": counts,
        "errors": errors,
        "request_count": request_count,
        "unprocessed": len(pending) - request_count,
        "source_terms": (
            "Riverside County / RCIT public OpenData; approximate assessment parcels, "
            "not surveyed boundaries or proposed project use"
        ),
        "coverage": "Bounded Riverside point lookup; no countywide completeness claim",
    }
    temporary = directory / "spatial-parcel-use.json.tmp"
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(directory / "spatial-parcel-use.json")
    return result


def main() -> None:
    from constructionsight.security_fit import rank_leads

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args()
    if not args.execute_live:
        parser.error("Explicit --execute-live required")
    rows = rank_leads(json.loads(args.snapshot.read_text())["rows"])
    with httpx.Client(timeout=40, follow_redirects=False) as client:
        print(json.dumps(collect(client, rows, args.data_dir)["counts"]))


if __name__ == "__main__":
    main()
