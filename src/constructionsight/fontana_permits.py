"""Official Fontana historical property-record queries; exact address candidates only.

Uses the anonymous HTTPS endpoint published by the city's linked LFPermits
frontend. Historical property co-occurrence is not a current-project permit match.
The observed response has no size, valuation, contractor, architect or issue date.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

URL = "https://web1.fontana.org/LFWebServices/LFWebService.asmx/LF_Permits"
PORTAL = "https://fontanaca.gov/3123/Historical-Property-Permit-Information"
ALIASES = {
    "AVENUE": "AVE",
    "BOULEVARD": "BLVD",
    "STREET": "ST",
    "ROAD": "RD",
    "DRIVE": "DR",
    "COURT": "CT",
    "LANE": "LN",
    "NORTH": "N",
    "SOUTH": "S",
    "EAST": "E",
    "WEST": "W",
}


def address(value: Any) -> str | None:
    text = str(value or "").upper().strip()
    if not re.fullmatch(r"\d{1,6}\s+[A-Z0-9 .]+", text):
        return None
    words = [ALIASES.get(w, w) for w in text.replace(".", "").split()]
    return " ".join(words)


def fetch_candidates(client: httpx.Client, lead: dict[str, Any]) -> dict[str, Any]:
    if (
        lead.get("SITE_COUNTY") != "San Bernardino"
        or str(lead.get("SITE_CITY") or "").casefold() != "fontana"
    ):
        raise ValueError("Only source-reported Fontana addresses are supported")
    full = address(lead.get("SITE_ADDRESS"))
    if not full:
        raise ValueError(
            "A single numeric street address is required; no intersection or fuzzy search"
        )
    number, street = full.split(" ", 1)
    with client.stream(
        "GET",
        URL,
        params={"StreetNumber": number, "StreetName": street, "CaseNumber": ""},
        follow_redirects=False,
    ) as response:
        if response.status_code != 200:
            raise ValueError(f"Fontana public search unavailable: HTTP {response.status_code}")
        parts = []
        count = 0
        for part in response.iter_bytes():
            count += len(part)
            if count > 2_000_000:
                raise ValueError("Fontana response exceeds limit")
            parts.append(part)
        raw = b"".join(parts)
        request_url = str(response.request.url)
    data = json.loads(raw)
    records = data.get("results") if isinstance(data, dict) else None
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise ValueError("Unexpected Fontana public search schema")
    matches = []
    for row in records:
        candidate = address(
            str(row.get("StreetNumber") or "") + " " + str(row.get("StreetName") or "")
        )
        if candidate != full or row.get("Unit"):
            continue
        matches.append(
            {
                k: row.get(k)
                for k in (
                    "StreetNumber",
                    "StreetName",
                    "PermitNumber",
                    "BuildingPermitType",
                    "CaseNumber",
                    "ProjectName",
                    "FinalInspectionDate",
                    "Tocid",
                )
            }
        )
    return {
        "source_key": lead["source_key"],
        "request_url": request_url,
        "portal_url": PORTAL,
        "captured_at": datetime.now(UTC).isoformat(),
        "response_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_response": raw.decode("utf-8"),
        "returned_records": len(records),
        "candidates": matches,
        "confidence": "exact_address_historical_property_candidate",
        "project_match_verified": False,
        "filled_dossier_fields": {},
    }


def retain_candidates(directory: Path, result: dict[str, Any]) -> None:
    file = directory / "fontana-permits.json"
    previous = json.loads(file.read_text()) if file.exists() else {}
    previous[result["source_key"]] = result
    temporary = directory / "fontana-permits.json.tmp"
    fd = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(previous, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(file)
