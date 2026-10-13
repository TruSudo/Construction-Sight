"""County-scoped Active SMARTS pagination, retained evidence, and complete-run comparison."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from constructionsight.smarts_api import COUNTIES, SmartsApiError, fetch_page
from constructionsight.smarts_evidence_ledger import record_smarts_page
from constructionsight.smarts_intake_bridge import build_smarts_intake_preview

PUBLIC_FIELDS = (
    "WDID",
    "APP_ID",
    "SITE_NAME",
    "SITE_ADDRESS",
    "SITE_CITY",
    "SITE_COUNTY",
    "SITE_LATITUDE",
    "SITE_LONGITUDE",
    "LATITUDE",
    "LONGITUDE",
    "STATUS",
    "DEVELOPER_NAME",
    "OWNER_NAME",
    "CONSTRUCTION_COMMENCEMENT_DATE",
    "NOT_EFFECTIVE_DATE",
    "NOI_PROCESSED_DATE",
    "COMPLETE_PROJECT_DATE",
)


def identities(rows: list[dict[str, Any]]) -> set[tuple[str, str, str]]:
    return {(str(row["SITE_COUNTY"]), str(row["WDID"]), str(row["APP_ID"])) for row in rows}


def collect_active(client: httpx.Client, directory: Path) -> dict[str, Any]:
    """Publish a local projection only after both county traversals finish successfully."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    cache = directory / "active.json"
    previous = json.loads(cache.read_text()) if cache.exists() else None
    rows: list[dict[str, Any]] = []
    pages = []
    totals = {}
    requests = 0
    missing_identity_rows = 0
    for county in COUNTIES:
        offset, total = 0, None
        county_rows: list[dict[str, Any]] = []
        seen_rows: dict[tuple[str, str, str], dict[str, Any]] = {}
        while total is None or offset < total:
            page = fetch_page(client, county=county, active_only=True, limit=100, offset=offset)
            requests += 1
            if total is not None and total != page.total:
                raise SmartsApiError(
                    "County count changed during pagination; previous run retained"
                )
            total = page.total
            if len(page.records) != min(100, total - offset):
                raise SmartsApiError("Truncated Active page; previous run retained")
            pages.append(
                {
                    "county": county,
                    "offset": offset,
                    "url": page.request_url,
                    "response_sha256": page.response_sha256,
                }
            )
            receipts = record_smarts_page(directory / "evidence.sqlite3", page)
            page_digests: set[str] = set()
            for record in page.records:
                preview = build_smarts_intake_preview(page, record)
                if preview.source_record_key is None:
                    missing_identity_rows += 1
                    continue
                if preview.record_sha256 in page_digests:
                    continue
                page_digests.add(preview.record_sha256)
                identity = next(iter(identities([record])))
                receipt = receipts[preview.record_sha256]
                if identity in seen_rows:
                    existing = seen_rows[identity]
                    existing["source_variants"] += 1
                    for key in PUBLIC_FIELDS:
                        if existing.get(key) != record.get(key):
                            existing[key] = None
                            if key not in existing["conflicting_fields"]:
                                existing["conflicting_fields"].append(key)
                    continue
                public: dict[str, Any] = {
                    **{key: record.get(key) for key in PUBLIC_FIELDS},
                    "source_key": receipt.source_record_key,
                    "row_sha256": receipt.row_sha256,
                    "response_sha256": receipt.response_sha256,
                    "source_variants": 1,
                    "conflicting_fields": [],
                }
                seen_rows[identity] = public
                county_rows.append(public)
            offset += len(page.records)
        rows.extend(county_rows)
        totals[county] = total
    current = identities(rows)
    old = identities(previous["rows"]) if previous else set()
    added = current - old if previous else set()
    removed = old - current if previous else set()
    now = datetime.now(UTC).isoformat()
    first_seen = (
        {tuple(item["identity"]): item["at"] for item in previous.get("first_seen", [])}
        if previous
        else {}
    )
    for identity in added:
        first_seen[identity] = now
    for row in rows:
        identity = next(iter(identities([row])))
        row["is_new"] = identity in added
        row["first_seen"] = first_seen.get(identity)
    result = {
        "rows": rows,
        "captured_at": now,
        "requests": requests,
        "totals": totals,
        "baseline": previous is None,
        "new_count": len(added),
        "missing_count": len(removed),
        "first_seen": [{"identity": list(k), "at": v} for k, v in first_seen.items()],
        "pages": pages,
        "duplicate_rows": sum(totals.values()) - len(rows) - missing_identity_rows,
        "missing_identity_rows": missing_identity_rows,
        "coverage": "Both county Active filters traversed; not all construction",
    }
    temporary = directory / "active.json.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(result, stream, separators=(",", ":"))
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(cache)
    return result
