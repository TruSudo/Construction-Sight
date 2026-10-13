"""Offline source-scoped SMARTS inspection corroboration preview.

Facility exports and inspection exports are operator-supplied. This never
fetches, persists, promotes lead readiness, or treats a regulator's inspection
as confirmation of physical construction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import stat
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from constructionsight.smarts_snapshot_diff import (
    COUNTIES,
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    MAX_PREVIEW_KEYS,
    FacilitySnapshot,
    SmartsSnapshotError,
    _source_id,
    load_facility_snapshot,
)

INSPECTION_RESOURCE = "33047e47-7d44-46aa-9e0f-1a0f1b0cad66"
REQUIRED_INSPECTION_COLUMNS = frozenset(
    {"APP_ID", "WDID", "INSPECTION_ID", "INSPECTION_DATE", "PLACE_COUNTY", "PERMIT_TYPE"}
)


@dataclass(frozen=True)
class InspectionEvidence:
    inspection_id: str
    source_key: str
    inspection_date: str | None
    row_sha256: str


@dataclass(frozen=True)
class InspectionReview:
    file_sha256: str
    input_rows: int
    selected_county_rows: int
    construction_rows: int
    linked: tuple[InspectionEvidence, ...]
    unmatched: int
    conflicted: int
    unverified_dates: int
    out_of_scope: int


def _inspection_id(value: str) -> str | None:
    value = value.strip()
    if re.fullmatch(r"[0-9]{1,18}(?:[.]0+)?", value) is None:
        return None
    identifier = value.split(".")[0]
    if not any(c != "0" for c in identifier):
        return None
    return identifier


def _inspection_date(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}(?:T[0-9:.+Z-]+)?", value) is None:
        return None
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError:
        return None


def _inspection_join(
    row: dict[str, str], facilities: FacilitySnapshot
) -> tuple[str | None, bool]:
    """Resolve source aliases only when all present identifiers agree."""
    app_id = _source_id(row["APP_ID"], kind="app_id")
    wdid = _source_id(row["WDID"], kind="wdid")
    aliases = [
        (kind, value) for kind, value in (("app_id", app_id), ("wdid", wdid))
        if value is not None
    ]
    if not aliases:
        return None, False
    matches = [
        facilities.alias_owners.get(alias) for alias in aliases
    ]
    known = {match for match in matches if match is not None}
    if len(known) > 1:
        return None, True
    if not known:
        return None, False
    # An inspection supplying an extra identifier absent from the facility row
    # cannot safely assert that the new alias belongs to that facility.
    if any(match is None for match in matches):
        return None, True
    return next(iter(known)), False


def review_inspections(path: Path, *, facilities: FacilitySnapshot) -> InspectionReview:
    """Strictly interpret the separate official SMARTS inspections CSV schema."""
    if facilities.county not in COUNTIES:
        raise SmartsSnapshotError("Unapproved inspection county")
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CSV_BYTES:
            raise SmartsSnapshotError("Inspections must be a bounded regular CSV")
        body = path.read_bytes()
    except OSError as exc:
        raise SmartsSnapshotError("Inspections CSV could not be read") from exc
    if not body or len(body) > MAX_CSV_BYTES:
        raise SmartsSnapshotError("Inspections file has an invalid size")
    file_sha = hashlib.sha256(body).hexdigest()
    try:
        text = body.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise SmartsSnapshotError("Inspections CSV must be UTF-8") from exc

    linked: list[InspectionEvidence] = []
    seen: set[str] = set()
    total = selected = construction = unmatched = conflicted = undated = scope = 0
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        fields = reader.fieldnames
        if (
            fields is None or any(not field for field in fields)
            or len(set(fields)) != len(fields)
            or not REQUIRED_INSPECTION_COLUMNS.issubset(fields)
        ):
            raise SmartsSnapshotError("SMARTS inspections CSV schema is incompatible")
        for row in reader:
            total += 1
            if total > MAX_CSV_ROWS:
                raise SmartsSnapshotError("Inspections row limit exceeded")
            if None in row or any(value is None for value in row.values()):
                raise SmartsSnapshotError("Malformed inspections CSV row")
            if row["PLACE_COUNTY"] != facilities.county:
                continue
            selected += 1
            permit_type = row["PERMIT_TYPE"].upper()
            if "CONSTRUCTION" not in permit_type:
                scope += 1
                continue
            construction += 1
            insp_id = _inspection_id(row["INSPECTION_ID"])
            if insp_id is None:
                conflicted += 1
                continue
            if insp_id in seen:
                raise SmartsSnapshotError("Duplicate inspection ID in selected construction rows")
            seen.add(insp_id)
            try:
                key, conflict = _inspection_join(row, facilities)
            except SmartsSnapshotError:
                conflicted += 1
                continue
            if conflict:
                conflicted += 1
                continue
            if key is None:
                unmatched += 1
                continue
            when = _inspection_date(row["INSPECTION_DATE"])
            if when is None:
                undated += 1
            semantic = {column: value for column, value in row.items() if column != "_id"}
            row_sha = hashlib.sha256(
                json.dumps(
                    semantic, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            linked.append(InspectionEvidence(insp_id, key, when, row_sha))
    except (csv.Error, UnicodeError, OverflowError) as exc:
        raise SmartsSnapshotError("Invalid inspections CSV") from exc
    if selected == 0:
        raise SmartsSnapshotError("No inspections rows for the approved county")
    return InspectionReview(
        file_sha, total, selected, construction, tuple(linked),
        unmatched, conflicted, undated, scope,
    )


def build_inspection_summary(
    facilities: FacilitySnapshot, inspection: InspectionReview
) -> dict[str, Any]:
    by_source: dict[str, list[InspectionEvidence]] = defaultdict(list)
    for event in inspection.linked:
        by_source[event.source_key].append(event)
    preview: list[dict[str, Any]] = []
    for key in sorted(by_source)[:MAX_PREVIEW_KEYS]:
        evidence = by_source[key]
        dates = [row.inspection_date for row in evidence if row.inspection_date is not None]
        preview.append({
            "source_key": key,
            "inspection_count": len(evidence),
            "latest_reported_inspection_date": max(dates) if dates else None,
            "inspection_evidence": [
                {"inspection_id": row.inspection_id, "row_sha256": row.row_sha256}
                for row in sorted(evidence, key=lambda item: item.inspection_id)[:5]
            ],
            "evidence_preview_truncated": len(evidence) > 5,
        })
    return {
        "ok": True,
        "source": "California SMARTS inspections (operator-supplied CSV)",
        "resource_id": INSPECTION_RESOURCE,
        "county": facilities.county,
        "facility_csv_sha256": facilities.file_sha256,
        "inspections_csv_sha256": inspection.file_sha256,
        "facility_count": facilities.selected_rows,
        "inspection_file_rows": inspection.input_rows,
        "inspection_county_rows": inspection.selected_county_rows,
        "construction_inspection_rows": inspection.construction_rows,
        "linked_inspection_rows": len(inspection.linked),
        "linked_facility_count": len(by_source),
        "unmatched": inspection.unmatched,
        "identity_conflicts": inspection.conflicted,
        "invalid_or_absent_dates_on_linked_rows": inspection.unverified_dates,
        "out_of_scope_permit_type": inspection.out_of_scope,
        "preview_truncated": len(by_source) > MAX_PREVIEW_KEYS,
        "review_preview": preview,
        "data_coverage": "unverified",
        "independent_parcel_verification": False,
        "construction_activity_proven": False,
        "security_demand_proven": False,
        "commercial_readiness": "blocked_pending_verification",
        "limitations": [
            "Inspection rows are compliance observations, not building permits.",
            "Only direct, county-scoped agreeing source IDs are accepted.",
            "Unknown permit type, missing IDs, mismatched aliases and cross-county"
            " observations do not produce automatic links.",
            "An inspection does not establish physical construction or bidding demand.",
            "Raw contact fields, personnel names, notes and exact site addresses are omitted.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline inspection corroboration against SMARTS facility CSV"
    )
    parser.add_argument("--county", choices=COUNTIES, required=True)
    parser.add_argument("--facilities", type=Path, required=True)
    parser.add_argument("--inspections", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.facilities.resolve() == args.inspections.resolve():
            raise SmartsSnapshotError("Facility and inspections sources must differ")
        facilities = load_facility_snapshot(args.facilities, county=args.county)
        inspections = review_inspections(args.inspections, facilities=facilities)
        result = build_inspection_summary(facilities, inspections)
        print(json.dumps(result, indent=2))
    except SmartsSnapshotError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
