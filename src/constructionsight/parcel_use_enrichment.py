"""Bounded, explicit Riverside parcel-use enrichment with exact address and retained bytes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from constructionsight.lead_quality import classify_names, load_keywords

LAYER = (
    "https://gis.countyofriverside.us/arcgis_mapping/rest/services/OpenData/Assessor/MapServer/50"
)
LABEL = "Source-claimed, from parcel use code"
FIELDS = "APN,SITUS_STREET,SITUS_CITY,CLASS_CODE,UNIT_NUMBER"
ABBREVIATIONS = {
    "STREET": "ST",
    "AVENUE": "AVE",
    "ROAD": "RD",
    "DRIVE": "DR",
    "COURT": "CT",
    "LANE": "LN",
    "BOULEVARD": "BLVD",
    "PLACE": "PL",
    "PARKWAY": "PKWY",
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
}


def normalized_address(value: Any) -> str | None:
    text = re.sub(r"[.,]", "", str(value or "").strip().upper())
    if not re.match(r"^\d+\s+[A-Z]", text):
        return None
    return " ".join(ABBREVIATIONS.get(t, t) for t in text.split())


def normalized_city(value: Any) -> str:
    text = " ".join(str(value or "").strip().upper().split())
    return re.sub(r"\s+CA(?:\s+\d{5}(?:-\d{4})?)?$", "", text)


def eligible_for_parcel_type(row: dict[str, Any]) -> bool:
    # Existing assessment use cannot resolve a contradictory agricultural project name.
    return row.get("project_type") == "unknown" and not re.search(
        r"\b(?:farms?|organic|agricultur\w*|orchards?|vineyards?)\b",
        str(row.get("SITE_NAME") or ""),
        re.I,
    )


def source_use_type(value: Any, *, site_name: str = "") -> dict[str, Any] | None:
    text = str(value or "").strip()
    # A numeric code without an official codebook is never decoded by guessing.
    if not text or not re.search(r"[A-Za-z]", text):
        return None
    if re.search(r"\b(grove|agricultural|farm|orchard|vineyard|mixed)\b", text, re.I):
        return None
    result = None
    for rule in load_keywords().get("parcel_use_rules", []):
        match = next(
            (
                k
                for k in rule["keywords"]
                if re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", text, re.I)
            ),
            None,
        )
        if match:
            result = {
                "project_type": rule["project_type"],
                "subtype": rule["subtype"],
                "matched_keyword": match,
                "excluded": False,
            }
            break
    if result is None:
        result = classify_names({"SITE_NAME": text})
    if result["project_type"] == "unknown":
        return None
    if result["project_type"] == "residential" and re.search(r"\bpark\b", site_name, re.I):
        return None  # A park name does not establish a proposed residential project.
    return {
        **result,
        "source": LABEL,
        "confidence": 0.5,
        "confidence_basis": (
            "Heuristic source-use signal; existing parcel use is not proposed project use"
        ),
        "evidence_field": "CLASS_CODE",
        "evidence_value": text,
        "verified": False,
    }


def claims_from_responses(
    rows: list[dict[str, Any]], responses: list[dict[str, Any]], directory: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    candidates: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for response in responses:
        if response.get("source_url", "").split("?")[0] != LAYER + "/query":
            raise ValueError("Only the reviewed official Riverside parcel source is accepted")
        path = (directory / response["path"]).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise ValueError("Parcel response path escapes the data folder")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != response["sha256"]:
            raise ValueError("Parcel response hash mismatch")
        payload = json.loads(raw)
        if payload.get("error") or payload.get("exceededTransferLimit"):
            raise ValueError("Parcel query incomplete or rejected; no claims accepted")
        for feature in payload["features"]:
            attrs = feature["attributes"]
            address = normalized_address(attrs.get("SITUS_STREET"))
            city = normalized_city(attrs.get("SITUS_CITY"))
            if address and city and attrs.get("APN"):
                candidates[(address, city)].append({**attrs, "response": response})
    claims = {}
    counts = {"eligible": 0, "ambiguous": 0, "no_match": 0, "unmapped_use": 0, "classified": 0}
    for row in rows:
        if row.get("SITE_COUNTY") != "Riverside" or not eligible_for_parcel_type(row):
            continue
        address, city = (
            normalized_address(row.get("SITE_ADDRESS")),
            normalized_city(row.get("SITE_CITY")),
        )
        if not address or not city:
            continue
        counts["eligible"] += 1
        matches = candidates.get((address, city), [])
        unique = {str(m["APN"]) for m in matches}
        if not unique:
            counts["no_match"] += 1
            continue
        if (
            len(unique) != 1
            or len({str(m["CLASS_CODE"]) for m in matches}) != 1
            or any(str(m.get("UNIT_NUMBER") or "").strip() for m in matches)
        ):
            counts["ambiguous"] += 1
            continue
        match = matches[0]
        classified = source_use_type(match["CLASS_CODE"], site_name=str(row.get("SITE_NAME") or ""))
        if not classified:
            counts["unmapped_use"] += 1
            continue
        claims[row["source_key"]] = {
            **classified,
            "apn": match["APN"],
            "address": address,
            "city": city,
            "county": "Riverside",
            "source_url": match["response"]["source_url"],
            "response_sha256": match["response"]["sha256"],
            "captured_at": match["response"]["captured_at"],
        }
        counts["classified"] += 1
    return claims, counts


def load_claims(directory: Path, rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    manifest = directory / "parcel-use.json"
    if not manifest.exists():
        return {}
    data = json.loads(manifest.read_text())
    claims, _ = claims_from_responses(rows, data["responses"], directory)
    return claims


def collect_parcel_use(
    client: httpx.Client, rows: list[dict[str, Any]], directory: Path
) -> dict[str, Any]:
    targets = [
        r
        for r in rows
        if r.get("SITE_COUNTY") == "Riverside"
        and eligible_for_parcel_type(r)
        and normalized_address(r.get("SITE_ADDRESS"))
    ]
    addresses = sorted(
        {str(r["SITE_ADDRESS"]).strip().upper() for r in targets}
        | {str(normalized_address(r["SITE_ADDRESS"])) for r in targets}
    )
    if len(addresses) > 2500:
        raise ValueError("Explicit bounded pass supports at most 2500 address forms")
    responses = []
    evidence = directory / "parcel-evidence"
    evidence.mkdir(parents=True, exist_ok=True, mode=0o700)
    for offset in range(0, len(addresses), 25):
        values = addresses[offset : offset + 25]
        where = (
            "UPPER(SITUS_STREET) IN ("
            + ",".join("'" + a.replace("'", "''") + "'" for a in values)
            + ")"
        )
        response = client.get(
            LAYER + "/query",
            params={
                "f": "json",
                "where": where,
                "outFields": FIELDS,
                "returnGeometry": "false",
                "resultRecordCount": 1000,
            },
        )
        # Includes 403: no fallback, retry, alternate headers or auth bypass.
        response.raise_for_status()
        if len(response.content) > 4_000_000:
            raise ValueError("Parcel response exceeds the bounded payload limit")
        payload = response.json()
        if payload.get("error") or payload.get("exceededTransferLimit"):
            raise ValueError("Parcel query incomplete or rejected")
        digest = hashlib.sha256(response.content).hexdigest()
        relative = "parcel-evidence/" + digest + ".json"
        (directory / relative).write_bytes(response.content)
        responses.append(
            {
                "source_url": str(response.url),
                "sha256": digest,
                "path": relative,
                "captured_at": datetime.now(UTC).isoformat(),
            }
        )
    claims, counts = claims_from_responses(rows, responses, directory)
    result = {
        "responses": responses,
        "counts": counts,
        "claims": claims,
        "coverage": "Bounded exact-address Riverside lookup only; not county completeness",
        "source_terms": (
            "Public county OpenData parcel service; RCIT attribution retained; "
            "assessor use is not permitted or proposed construction use"
        ),
    }
    temporary = directory / "parcel-use.json.tmp"
    temporary.write_text(json.dumps(result, indent=2) + "\n")
    temporary.replace(directory / "parcel-use.json")
    return result


def main() -> None:
    from constructionsight.security_fit import rank_leads

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args()
    if not args.execute_live:
        parser.error("Explicit --execute-live is required; no source requests on preview")
    snapshot = json.loads(args.snapshot.read_text())
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        result = collect_parcel_use(client, rank_leads(snapshot["rows"]), args.data_dir)
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
