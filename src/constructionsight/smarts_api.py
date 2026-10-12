"""Bounded, read-only SMARTS CKAN DataStore observations.

No scheduler, persistence, discovery of private endpoints, or implicit network
execution. Resource identities are taken from the official California catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from typing import Any

import httpx

API_URL = "https://publish.data.ca.gov/api/3/action/datastore_search"
SQL_API_URL = "https://publish.data.ca.gov/api/3/action/datastore_search_sql"
RESOURCE_IDS = {
    "facilities": "8a0ed456-ca69-4b29-9c5b-5de3958dc963",
    "inspections": "33047e47-7d44-46aa-9e0f-1a0f1b0cad66",
}
COUNTIES = ("San Bernardino", "Riverside")
MAX_PAGE_SIZE = 100
MAX_RESPONSE_BYTES = 2_000_000
MAX_STATUS_ROWS = 32
MAX_CANDIDATES = 25
USER_AGENT = "ConstructionSight/0.1 (public-data read-only research)"
FACILITIES_TABLE = '"' + RESOURCE_IDS["facilities"] + '"'
CANDIDATE_FIELDS = (
    "_id", "APP_ID", "WDID", "SITE_COUNTY", "SITE_CITY", "STATUS",
    "NOI_PROCESSED_DATE", "CONSTRUCTION_COMMENCEMENT_DATE", "NOT_EFFECTIVE_DATE",
)


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
    raw_response_bytes: bytes | None = None  # bounded decoded HTTP body for opt-in retention


@dataclass(frozen=True)
class SmartsSqlObservation:
    """A bounded SQL result, with response-byte evidence and no contact fields."""

    kind: str
    county: str
    request_url: str
    response_sha256: str
    records: tuple[dict[str, Any], ...]


def _approved_county(county: str) -> str:
    if type(county) is not str or county not in COUNTIES:
        raise SmartsApiError("Unapproved facility county")
    return COUNTIES[COUNTIES.index(county)]


def _fetch_sql_records(
    client: httpx.Client, *, sql: str, max_rows: int
) -> tuple[str, str, list[dict[str, Any]]]:
    """Execute one fixed-shape SQL request; never expose response text on error."""
    try:
        with client.stream(
            "GET", SQL_API_URL, params={"sql": sql}, follow_redirects=False
        ) as response:
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
    records = result.get("records")
    if not isinstance(records, list) or len(records) > max_rows or not all(
        isinstance(record, dict) for record in records
    ):
        raise SmartsApiError("Invalid or oversized SQL records")
    return request_url, hashlib.sha256(body).hexdigest(), records


def fetch_status_summary(
    client: httpx.Client, *, county: str
) -> SmartsSqlObservation:
    """Count regulatory statuses for one approved county, without raw rows."""
    county = _approved_county(county)
    sql = (
        'SELECT "SITE_COUNTY", "STATUS", COUNT(*) AS n '
        f'FROM {FACILITIES_TABLE} WHERE "SITE_COUNTY" = \'{county}\' '
        'GROUP BY "SITE_COUNTY", "STATUS" ORDER BY "STATUS" ASC '
        f"LIMIT {MAX_STATUS_ROWS}"
    )
    request_url, digest, records = _fetch_sql_records(
        client, sql=sql, max_rows=MAX_STATUS_ROWS
    )
    if len(records) == MAX_STATUS_ROWS:
        raise SmartsApiError("Status summary may be truncated")
    statuses: set[str] = set()
    for record in records:
        status = record.get("STATUS")
        count = record.get("n")
        if (set(record) != {"SITE_COUNTY", "STATUS", "n"}
                or record.get("SITE_COUNTY") != county
                or type(status) is not str or not status
                or type(count) is not int or count < 1 or status in statuses):
            raise SmartsApiError("Invalid status summary row")
        statuses.add(status)
    return SmartsSqlObservation(
        "status-summary", county, request_url, digest, tuple(records)
    )


def fetch_recent_candidates(
    client: httpx.Client, *, county: str, limit: int = 10
) -> SmartsSqlObservation:
    """Get recent NOI records as leads for review, not construction evidence."""
    county = _approved_county(county)
    if type(limit) is not int or not 1 <= limit <= MAX_CANDIDATES:
        raise SmartsApiError("Invalid candidate limit")
    columns = ", ".join(f'"{field}"' for field in CANDIDATE_FIELDS)
    sql = (
        f"SELECT {columns} FROM {FACILITIES_TABLE} "
        f'WHERE "SITE_COUNTY" = \'{county}\' '
        'AND "NOI_PROCESSED_DATE" IS NOT NULL '
        'ORDER BY "NOI_PROCESSED_DATE" DESC, "_id" DESC '
        f"LIMIT {limit}"
    )
    request_url, digest, records = _fetch_sql_records(client, sql=sql, max_rows=limit)
    seen: set[str] = set()
    for record in records:
        transport_id = record.get("_id")
        processed = record.get("NOI_PROCESSED_DATE")
        if (not set(record).issubset(CANDIDATE_FIELDS)
                or not all(field in record for field in CANDIDATE_FIELDS)
                or record.get("SITE_COUNTY") != county
                or type(transport_id) not in (int, str)
                or not str(transport_id)
                or str(transport_id) in seen
                or type(processed) is not str or not processed):
            raise SmartsApiError("Invalid candidate row")
        seen.add(str(transport_id))
    return SmartsSqlObservation(
        "recent-candidates", county, request_url, digest, tuple(records)
    )


def fetch_page(
    client: httpx.Client,
    *,
    resource: str = "facilities",
    county: str | None = None,
    limit: int = 3,
    offset: int = 0,
    app_id: str | None = None,
    wdid: str | None = None,
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
    if app_id is not None or wdid is not None:
        if resource != "facilities" or county not in COUNTIES:
            raise SmartsApiError("Exact facility lookup requires an approved county")
        if (app_id is None) == (wdid is None):
            raise SmartsApiError("Choose one facility record identifier")
        if app_id is not None and (
            not re.fullmatch(r"[0-9]{1,15}", app_id)
            or not any(ch != "0" for ch in app_id)
        ):
            raise SmartsApiError("APP_ID must be a numeric source identifier, not NA")
        if wdid is not None and (not re.fullmatch(r"[A-Za-z0-9 ]{2,32}", wdid) or not wdid.strip()):
            raise SmartsApiError("Invalid WDID source identifier")

    params: dict[str, str | int] = {
        "resource_id": RESOURCE_IDS[resource],
        "limit": limit,
        "offset": offset,
    }
    if county is not None:
        filters = {"SITE_COUNTY": county}
        if app_id is not None:
            filters["APP_ID"] = app_id
        if wdid is not None:
            filters["WDID"] = wdid
        params["filters"] = json.dumps(filters, separators=(",", ":"))

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

    if app_id is not None and any(row.get("APP_ID") != app_id for row in rows):
        raise SmartsApiError("APP_ID filter returned a different record")
    if wdid is not None and any(row.get("WDID") != wdid for row in rows):
        raise SmartsApiError("WDID filter returned a different record")
    if county is not None and any(row.get("SITE_COUNTY") != county for row in rows):
        raise SmartsApiError("County filter returned a different record")

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
        raw_response_bytes=body,
    )


def fetch_exact_facility(
    client: httpx.Client, *, county: str,
    app_id: str | None = None, wdid: str | None = None,
) -> SmartsPage:
    """Resolve exactly one record in an approved county; never guess on duplicates."""
    if (app_id is None) == (wdid is None):
        raise SmartsApiError("Provide exactly one APP_ID or WDID")
    page = fetch_page(
        client, resource="facilities", county=county,
        app_id=app_id, wdid=wdid, limit=2,
    )
    if page.total != 1 or len(page.records) != 1:
        raise SmartsApiError("Exact facility lookup was missing or ambiguous")
    return page


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
    parser.add_argument(
        "--mode", choices=("page", "status-summary", "recent-candidates"), default="page"
    )
    parser.add_argument("--resource", choices=tuple(RESOURCE_IDS), default="facilities")
    parser.add_argument("--county", choices=COUNTIES)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_live:
        parser.error("Live access requires --execute-live")
    if args.mode != "page" and (args.county is None or args.resource != "facilities"):
        parser.error("SQL modes require an approved facility county")
    if args.mode == "status-summary" and args.limit != 3:
        parser.error("Status summary does not accept a page limit")
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            if args.mode == "status-summary":
                observation = fetch_status_summary(client, county=args.county)
            elif args.mode == "recent-candidates":
                observation = fetch_recent_candidates(
                    client, county=args.county, limit=args.limit
                )
            else:
                page = fetch_page(
                    client, resource=args.resource, county=args.county, limit=args.limit
                )
    except SmartsApiError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    if args.mode != "page":
        print(json.dumps({
            "ok": True,
            "mode": observation.kind,
            "county_filter": observation.county,
            "records_received": len(observation.records),
            "request_url": observation.request_url,
            "response_sha256": observation.response_sha256,
            "regulatory_status_is_construction_activity": False,
            "reported_commencement_is_verified_activity": False,
            "records": observation.records,
        }, indent=2))
        return 0
    # Only curated non-contact information is printed; no live records are persisted.
    safe_fields = (
        "APP_ID", "WDID", "SITE_COUNTY", "SITE_CITY",
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
        "fields": [field for field in page.fields if field in safe_fields],
        "sample": [{key: row[key] for key in safe_fields if key in row}
                   for row in page.records],
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
