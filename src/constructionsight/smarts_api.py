"""Bounded, read-only SMARTS CKAN DataStore observations.

No scheduler, persistence, discovery of private endpoints, or implicit network
execution. Resource identities are taken from the official California catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from typing import Any

import httpx

API_URL = "https://publish.data.ca.gov/api/3/action/datastore_search"
RESOURCE_IDS = {
    "facilities": "8a0ed456-ca69-4b29-9c5b-5de3958dc963",
    "inspections": "33047e47-7d44-46aa-9e0f-1a0f1b0cad66",
}
COUNTIES = ("San Bernardino", "Riverside")
MAX_PAGE_SIZE = 100
MAX_RESPONSE_BYTES = 2_000_000
USER_AGENT = "ConstructionSight/0.1 (public-data read-only research)"


class SmartsApiError(ValueError):
    """A response is unavailable, incomplete, or cannot be trusted."""


@dataclass(frozen=True)
class SmartsPage:
    resource: str
    county: str | None
    offset: int
    limit: int
    total: int
    request_url: str
    response_sha256: str
    fields: tuple[str, ...]
    records: tuple[dict[str, Any], ...]


def fetch_page(
    client: httpx.Client,
    *,
    resource: str = "facilities",
    county: str | None = None,
    limit: int = 3,
    offset: int = 0,
) -> SmartsPage:
    """Fetch exactly one controlled public page, without retries or redirects."""
    if resource not in RESOURCE_IDS:
        raise SmartsApiError("Unapproved SMARTS resource")
    if county is not None and (resource != "facilities" or county not in COUNTIES):
        raise SmartsApiError("County filters are approved only for named facility counties")
    if type(limit) is not int or not 1 <= limit <= MAX_PAGE_SIZE:
        raise SmartsApiError("Invalid page size")
    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise SmartsApiError("Invalid offset")

    params = {
        "resource_id": RESOURCE_IDS[resource],
        "limit": limit,
        "offset": offset,
    }
    if county is not None:
        params["filters"] = json.dumps({"SITE_COUNTY": county}, separators=(",", ":"))

    try:
        with client.stream("GET", API_URL, params=params, follow_redirects=False) as response:
            if response.status_code != 200:
                raise SmartsApiError("Unexpected HTTP status: " + str(response.status_code))
            media_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if media_type != "application/json":
                raise SmartsApiError("Expected a JSON response")
            chunks: list[bytes] = []
            body_size = 0
            for chunk in response.iter_bytes():
                body_size += len(chunk)
                if body_size > MAX_RESPONSE_BYTES:
                    raise SmartsApiError("Response exceeded the byte limit")
                chunks.append(chunk)
            body = b"".join(chunks)
            request_url = str(response.request.url)
    except httpx.HTTPError as exc:
        raise SmartsApiError("SMARTS transport failed: " + type(exc).__name__) from exc

    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise SmartsApiError("Invalid response JSON") from exc
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise SmartsApiError("CKAN did not report success")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise SmartsApiError("Missing result object")
    if result.get("resource_id", RESOURCE_IDS[resource]) != RESOURCE_IDS[resource]:
        raise SmartsApiError("Response resource identity mismatch")
    total = result.get("total")
    rows = result.get("records")
    fields_raw = result.get("fields")
    if type(total) is not int or total < 0 or not isinstance(rows, list):
        raise SmartsApiError("Invalid count or records")
    if len(rows) > limit or len(rows) > total or offset + len(rows) > total:
        raise SmartsApiError("Page size and count disagree")
    if offset < total and not rows:
        raise SmartsApiError("Incomplete nonempty page")
    if not all(isinstance(row, dict) for row in rows):
        raise SmartsApiError("Malformed record")
    if not isinstance(fields_raw, list) or not all(
        isinstance(field, dict) and isinstance(field.get("id"), str) for field in fields_raw
    ):
        raise SmartsApiError("Invalid field metadata")
    fields = tuple(field["id"] for field in fields_raw)
    if len(set(fields)) != len(fields) or "_id" not in fields:
        raise SmartsApiError("Missing or duplicate transport row identifier")
    if resource == "facilities" and not {"APP_ID", "WDID", "SITE_COUNTY"}.issubset(fields):
        raise SmartsApiError("Required facility fields missing")
    if resource == "inspections" and not {"APP_ID", "WDID"}.issubset(fields):
        raise SmartsApiError("Required inspection fields missing")
    if any("_id" not in row or not set(row).issubset(fields) for row in rows):
        raise SmartsApiError("Malformed row identity or schema")

    return SmartsPage(
        resource=resource,
        county=county,
        offset=offset,
        limit=limit,
        total=total,
        request_url=request_url,
        response_sha256=hashlib.sha256(body).hexdigest(),
        fields=fields,
        records=tuple(rows),
    )


def fetch_bounded_snapshot(
    client: httpx.Client,
    *,
    resource: str = "facilities",
    county: str | None = None,
    page_size: int = 50,
    max_records: int = 500,
) -> tuple[SmartsPage, ...]:
    """Collect a small snapshot; fail on pagination drift and duplicate transport IDs.

    This does not prove consistency under concurrent source updates. For production,
    reconcile a published CSV snapshot or use a documented stable change feed.
    """
    if type(max_records) is not int or not 1 <= max_records <= 500:
        raise SmartsApiError("Snapshot budget must be 1..500")
    if type(page_size) is not int or not 1 <= page_size <= MAX_PAGE_SIZE:
        raise SmartsApiError("Invalid page size")
    pages: list[SmartsPage] = []
    seen: set[str] = set()
    total: int | None = None
    offset = 0
    while True:
        page = fetch_page(
            client, resource=resource, county=county,
            limit=min(page_size, max_records - offset), offset=offset,
        )
        if total is None:
            total = page.total
            if total > max_records:
                raise SmartsApiError("Source exceeds bounded snapshot budget")
        elif page.total != total or page.fields != pages[0].fields:
            raise SmartsApiError("Source changed during pagination")
        for row in page.records:
            transport_id = str(row["_id"])
            if transport_id in seen:
                raise SmartsApiError("Duplicate transport row across pages")
            seen.add(transport_id)
        pages.append(page)
        offset += len(page.records)
        if offset == total:
            return tuple(pages)
        if offset >= max_records or not page.records:
            raise SmartsApiError("Incomplete snapshot")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit, bounded SMARTS public API probe")
    parser.add_argument("--resource", choices=tuple(RESOURCE_IDS), default="facilities")
    parser.add_argument("--county", choices=COUNTIES)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_live:
        parser.error("Live access requires --execute-live")
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            page = fetch_page(client, resource=args.resource, county=args.county, limit=args.limit)
    except SmartsApiError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    # Only curated non-contact information is printed; no live records are persisted.
    safe_fields = (
        "APP_ID", "WDID", "SITE_COUNTY", "SITE_CITY", "SITE_NAME",
        "STATUS", "CONSTRUCTION_COMMENCEMENT_DATE", "INSPECTION_DATE",
    )
    print(json.dumps({
        "ok": True,
        "resource": page.resource,
        "county_filter": page.county,
        "source_reported_total": page.total,
        "records_received": len(page.records),
        "request_url": page.request_url,
        "response_sha256": page.response_sha256,
        "fields": list(page.fields),
        "sample": [{key: row[key] for key in safe_fields if key in row}
                   for row in page.records],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
