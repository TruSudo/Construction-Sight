"""Offline SMARTS violations/enforcement source-corroboration preview.

This module does not infer a violation finding, guilt, active construction,
security demand, or commercial suitability from a source row.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import stat
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from constructionsight.smarts_inspection_review import (
    _inspection_date,
    _inspection_id,
    _inspection_join,
)
from constructionsight.smarts_snapshot_diff import (
    COUNTIES,
    MAX_CSV_BYTES,
    MAX_CSV_ROWS,
    MAX_PREVIEW_KEYS,
    FacilitySnapshot,
    SmartsSnapshotError,
    load_facility_snapshot,
)

ComplianceKind = Literal["violations", "enforcement"]
_RESOURCE = {
    "violations": ("9b69a654-0c9a-4865-8d10-38c55b1b8c58", "VIOLATION_ID", "OCCURRENCE_DATE"),
    "enforcement": ("9cf197f4-f1d5-4d43-b94b-ccb155ef14cf", "ENFORCEMENT_ID", "ISSUANCE_DATE"),
}
_REQUIRED_BASE = frozenset({"APP_ID", "WDID", "PERMIT_TYPE", "PLACE_COUNTY"})


@dataclass(frozen=True)
class ComplianceEvidence:
    source_key: str
    record_id: str
    reported_date: str | None
    row_sha256: str


@dataclass(frozen=True)
class ComplianceReview:
    kind: ComplianceKind
    file_sha256: str
    file_rows: int
    selected_county_rows: int
    construction_rows: int
    linked: tuple[ComplianceEvidence, ...]
    unmatched: int
    conflicts: int
    unknown_dates: int
    non_construction: int


def review_compliance(
    path: Path, *, kind: ComplianceKind, facilities: FacilitySnapshot
) -> ComplianceReview:
    if kind not in _RESOURCE or facilities.county not in COUNTIES:
        raise SmartsSnapshotError("Invalid SMARTS compliance resource or county")
    _, id_field, date_field = _RESOURCE[kind]
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CSV_BYTES:
            raise SmartsSnapshotError("Compliance CSV must be a bounded regular file")
        raw = path.read_bytes()
    except OSError as exc:
        raise SmartsSnapshotError("Compliance CSV could not be read") from exc
    if not raw or len(raw) > MAX_CSV_BYTES:
        raise SmartsSnapshotError("Compliance CSV is missing or oversized")
    file_sha = hashlib.sha256(raw).hexdigest()
    try:
        decoded = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise SmartsSnapshotError("Compliance CSV must be UTF-8") from exc

    evidence: list[ComplianceEvidence] = []
    seen: set[str] = set()
    total = selected = construction = unmatched = conflicted = undated = outscope = 0
    try:
        reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
        headers = reader.fieldnames
        if (
            headers is None or any(not value for value in headers)
            or len(set(headers)) != len(headers)
            or not (_REQUIRED_BASE | {id_field, date_field}).issubset(headers)
        ):
            raise SmartsSnapshotError("Invalid SMARTS compliance source schema")
        for row in reader:
            total += 1
            if total > MAX_CSV_ROWS:
                raise SmartsSnapshotError("Compliance row budget exceeded")
            if None in row or any(value is None for value in row.values()):
                raise SmartsSnapshotError("Malformed compliance CSV row")
            if row["PLACE_COUNTY"] != facilities.county:
                continue
            selected += 1
            if not row["PERMIT_TYPE"].strip().upper().startswith("CONSTRUCTION"):
                outscope += 1
                continue
            construction += 1
            record_id = _inspection_id(row[id_field])
            if record_id is None:
                conflicted += 1
                continue
            if record_id in seen:
                raise SmartsSnapshotError("Duplicate compliance source ID")
            seen.add(record_id)
            try:
                source_key, conflict = _inspection_join(row, facilities)
            except SmartsSnapshotError:
                conflicted += 1
                continue
            if conflict:
                conflicted += 1
                continue
            if source_key is None:
                unmatched += 1
                continue
            reported = _inspection_date(row[date_field])
            if reported is None:
                undated += 1
            semantic = {key: value for key, value in row.items() if key != "_id"}
            row_digest = hashlib.sha256(
                json.dumps(
                    semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest()
            evidence.append(ComplianceEvidence(source_key, record_id, reported, row_digest))
    except (csv.Error, OverflowError, UnicodeError) as exc:
        raise SmartsSnapshotError("Malformed compliance CSV") from exc
    if selected == 0:
        raise SmartsSnapshotError("No matching county compliance records in CSV")
    return ComplianceReview(
        kind, file_sha, total, selected, construction, tuple(evidence),
        unmatched, conflicted, undated, outscope,
    )


def build_compliance_summary(
    facilities: FacilitySnapshot, review: ComplianceReview
) -> dict[str, Any]:
    groups: dict[str, list[ComplianceEvidence]] = defaultdict(list)
    for record in review.linked:
        groups[record.source_key].append(record)
    previews: list[dict[str, Any]] = []
    for key in sorted(groups)[:MAX_PREVIEW_KEYS]:
        records = groups[key]
        dates = [record.reported_date for record in records if record.reported_date]
        previews.append({
            "source_key": key,
            "record_count": len(records),
            "latest_source_reported_date": max(dates) if dates else None,
            "evidence": [
                {"record_id": record.record_id, "row_sha256": record.row_sha256}
                for record in sorted(records, key=lambda record: record.record_id)[:5]
            ],
            "evidence_preview_truncated": len(records) > 5,
        })
    return {
        "ok": True,
        "kind": review.kind,
        "resource_id": _RESOURCE[review.kind][0],
        "county": facilities.county,
        "facility_file_sha256": facilities.file_sha256,
        "compliance_file_sha256": review.file_sha256,
        "source_file_rows": review.file_rows,
        "source_county_rows": review.selected_county_rows,
        "construction_permit_type_rows": review.construction_rows,
        "linked_records": len(review.linked),
        "linked_facility_count": len(groups),
        "unmatched": review.unmatched,
        "identity_conflicts": review.conflicts,
        "unverified_dates": review.unknown_dates,
        "out_of_scope_permit_type": review.non_construction,
        "review_preview": previews,
        "review_preview_truncated": len(groups) > MAX_PREVIEW_KEYS,
        "county_coverage": "unverified",
        "regulatory_findings_adjudicated": False,
        "physical_construction_verified": False,
        "commercial_readiness": "blocked_pending_verification",
        "limitations": [
            "Regulatory source reporting is not independent adjudication of liability.",
            "Only direct, agreeing APP_ID/WDID source-scoped associations are reported.",
            "Regulatory history is never a proxy for construction work or buyer demand.",
            "No free-text descriptions, individuals, or contact information are emitted.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline SMARTS compliance evidence review")
    parser.add_argument("--county", choices=COUNTIES, required=True)
    parser.add_argument("--facilities", type=Path, required=True)
    parser.add_argument("--resource", choices=tuple(_RESOURCE), required=True)
    parser.add_argument("--compliance", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.facilities.resolve() == args.compliance.resolve():
            raise SmartsSnapshotError("Compliance file must differ from facility source")
        facilities = load_facility_snapshot(args.facilities, county=args.county)
        record = review_compliance(args.compliance, kind=args.resource, facilities=facilities)
        print(json.dumps(build_compliance_summary(facilities, record), indent=2))
    except SmartsSnapshotError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
