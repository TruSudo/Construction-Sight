"""Offline, source-scoped SMARTS facility CSV comparison for human review.

No network, writes, scheduling, source completeness certification, site matching,
or lead promotion. A missing row is *not* proof of a deletion. Source CSVs must
be obtained and retained separately under an authorized acquisition process.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

COUNTIES = ("San Bernardino", "Riverside")
MAX_CSV_BYTES = 128 * 1024 * 1024
MAX_CSV_ROWS = 250_000
MAX_PREVIEW_KEYS = 25
REQUIRED_COLUMNS = frozenset({"APP_ID", "WDID", "SITE_COUNTY"})
_EMPTY = frozenset({"", "NA", "N/A", "NONE", "NULL", "UNKNOWN", "NOT AVAILABLE", "0"})
DiffKind = Literal["new", "changed", "unchanged", "missing_from_new"]


class SmartsSnapshotError(ValueError):
    """Input snapshot or comparison cannot be trusted for a reviewable diff."""


@dataclass(frozen=True)
class SnapshotRow:
    row_sha256: str
    app_id: str | None
    wdid: str | None


@dataclass(frozen=True)
class FacilitySnapshot:
    county: str
    file_sha256: str
    column_names: tuple[str, ...]
    total_rows: int
    selected_rows: int
    source_rows: dict[str, SnapshotRow]
    alias_owners: dict[tuple[str, str], str]


@dataclass(frozen=True)
class SnapshotEvent:
    source_key: str
    outcome: DiffKind
    previous_row_sha256: str | None
    current_row_sha256: str | None


def _source_id(value: str, *, kind: str) -> str | None:
    result = value.strip()
    if result.upper() in _EMPTY:
        return None
    if kind == "app_id":
        if re.fullmatch(r"[0-9]{1,15}", result) is None or not any(d != "0" for d in result):
            raise SmartsSnapshotError("Invalid APP_ID in selected county")
    elif re.fullmatch(r"[A-Za-z0-9 ]{2,32}", result) is None:
        raise SmartsSnapshotError("Invalid WDID in selected county")
    return result


def load_facility_snapshot(path: Path, *, county: str) -> FacilitySnapshot:
    """Read one local CSV, returning hashes and source keys, never contact fields."""
    if county not in COUNTIES:
        raise SmartsSnapshotError("Unapproved facility county")
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CSV_BYTES:
            raise SmartsSnapshotError("Snapshot must be a bounded regular CSV file")
        data = path.read_bytes()
    except OSError as exc:
        raise SmartsSnapshotError("Snapshot could not be read") from exc
    return parse_facility_snapshot_bytes(data, county=county)


def parse_facility_snapshot_bytes(data: bytes, *, county: str) -> FacilitySnapshot:
    """Validate original, bounded CSV bytes without writing a temporary file."""
    if county not in COUNTIES:
        raise SmartsSnapshotError("Unapproved facility county")
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_CSV_BYTES:
        raise SmartsSnapshotError("Snapshot has an invalid byte count")
    file_digest = hashlib.sha256(data).hexdigest()
    try:
        text = data.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise SmartsSnapshotError("Snapshot must use UTF-8") from exc

    rows: dict[str, SnapshotRow] = {}
    aliases: dict[tuple[str, str], str] = {}
    total = 0
    selected = 0
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames
        if (
            headers is None
            or any(not header for header in headers)
            or len(set(headers)) != len(headers)
            or not REQUIRED_COLUMNS.issubset(headers)
        ):
            raise SmartsSnapshotError("Missing, empty, or duplicate SMARTS CSV header")
        for record in reader:
            total += 1
            if total > MAX_CSV_ROWS:
                raise SmartsSnapshotError("Snapshot row budget exceeded")
            if None in record or any(value is None for value in record.values()):
                raise SmartsSnapshotError("Malformed SMARTS CSV row")
            if record["SITE_COUNTY"] != county:
                continue
            selected += 1
            app_id = _source_id(record["APP_ID"], kind="app_id")
            wdid = _source_id(record["WDID"], kind="wdid")
            if app_id is None and wdid is None:
                raise SmartsSnapshotError("Selected county row has no stable source identity")
            source_key = (
                f"smarts:facility:{county}:wdid:{wdid}" if wdid is not None
                else f"smarts:facility:{county}:app_id:{app_id}"
            )
            if source_key in rows:
                raise SmartsSnapshotError("Duplicate source identity in snapshot")
            # CSV has all-text cells: do not equate this to a typed CKAN JSON digest.
            semantic = {field: value for field, value in record.items() if field != "_id"}
            row_digest = hashlib.sha256(
                json.dumps(
                    semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest()
            rows[source_key] = SnapshotRow(row_digest, app_id, wdid)
            for kind, value in (("app_id", app_id), ("wdid", wdid)):
                if value is None:
                    continue
                alias = (kind, value)
                if alias in aliases:
                    raise SmartsSnapshotError("Duplicate APP_ID or WDID alias in snapshot")
                aliases[alias] = source_key
    except (csv.Error, UnicodeError, OverflowError) as exc:
        raise SmartsSnapshotError("Malformed or oversized SMARTS CSV") from exc
    if selected == 0:
        raise SmartsSnapshotError("No records found for the approved county")
    return FacilitySnapshot(county, file_digest, tuple(headers), total, selected, rows, aliases)


def reconcile_snapshots(
    previous: FacilitySnapshot, current: FacilitySnapshot
) -> tuple[SnapshotEvent, ...]:
    """Compare candidate source identities, failing closed on alias or schema drift."""
    if previous.county != current.county:
        raise SmartsSnapshotError("Cannot reconcile different counties")
    if previous.column_names != current.column_names:
        raise SmartsSnapshotError("SMARTS CSV schema changed; manual mapping review required")
    for alias in previous.alias_owners.keys() & current.alias_owners.keys():
        if previous.alias_owners[alias] != current.alias_owners[alias]:
            raise SmartsSnapshotError("SMARTS source identity drift requires manual review")
    for source_key in previous.source_rows.keys() & current.source_rows.keys():
        older = previous.source_rows[source_key]
        newer = current.source_rows[source_key]
        if (older.app_id, older.wdid) != (newer.app_id, newer.wdid):
            raise SmartsSnapshotError("SMARTS source alias changed; manual review required")

    events: list[SnapshotEvent] = []
    for key in sorted(previous.source_rows.keys() | current.source_rows.keys()):
        old = previous.source_rows.get(key)
        new = current.source_rows.get(key)
        outcome: DiffKind
        if old is None:
            outcome = "new"
        elif new is None:
            outcome = "missing_from_new"
        elif old.row_sha256 == new.row_sha256:
            outcome = "unchanged"
        else:
            outcome = "changed"
        events.append(
            SnapshotEvent(
                key, outcome, old.row_sha256 if old else None,
                new.row_sha256 if new else None,
            )
        )
    return tuple(events)


def build_review_summary(
    previous: FacilitySnapshot, current: FacilitySnapshot, events: tuple[SnapshotEvent, ...]
) -> dict[str, object]:
    """Render a redacted digest/identifier-only summary; no personal CSV columns."""
    counts = {
        kind: sum(event.outcome == kind for event in events)
        for kind in ("new", "changed", "unchanged", "missing_from_new")
    }
    review = [event for event in events if event.outcome != "unchanged"]
    return {
        "ok": True,
        "source": "California SMARTS facilities (operator-supplied CSV)",
        "county": previous.county,
        "previous_file_sha256": previous.file_sha256,
        "current_file_sha256": current.file_sha256,
        "previous_file_rows": previous.total_rows,
        "current_file_rows": current.total_rows,
        "previous_county_rows": previous.selected_rows,
        "current_county_rows": current.selected_rows,
        "counts": counts,
        "coverage_status": "unverified",
        "missing_from_new_is_deletion": False,
        "source_identity_is_project_identity": False,
        "commercial_readiness": "blocked_pending_verification",
        "review_count": len(review),
        "review_preview_truncated": len(review) > MAX_PREVIEW_KEYS,
        "review_preview": [
            {
                "source_key": item.source_key,
                "outcome": item.outcome,
                "previous_row_sha256": item.previous_row_sha256,
                "current_row_sha256": item.current_row_sha256,
            }
            for item in review[:MAX_PREVIEW_KEYS]
        ],
        "limitations": [
            "The CSV files must be independently established as authoritative,"
            " complete, time-specific source snapshots before county-wide conclusions.",
            "Absence in a later CSV is a review flag, not evidence of permit expiry,"
            " cancellation or physical completion.",
            "CSV string-value row hashes are not interchangeable with typed CKAN JSON hashes.",
            "No construction activity, parcel/project association or bidding"
            " readiness is inferred.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline SMARTS CSV change-review preview")
    parser.add_argument("--county", choices=COUNTIES, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.previous.resolve() == args.current.resolve():
            raise SmartsSnapshotError("Two independently retained snapshots are required")
        previous = load_facility_snapshot(args.previous, county=args.county)
        current = load_facility_snapshot(args.current, county=args.county)
        events = reconcile_snapshots(previous, current)
        print(json.dumps(build_review_summary(previous, current, events), indent=2))
    except SmartsSnapshotError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
