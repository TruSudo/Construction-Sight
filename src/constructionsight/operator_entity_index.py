"""Bounded read-only inventory of exact stored entity keys in retained source records."""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from constructionsight.operator_dashboard_models import (
    EntityIndexEntry,
    EntityIndexSnapshot,
    RecordSelection,
)
from constructionsight.storage.operator_read_store import read_project_page

ENTITY_INDEX_SCAN_LIMIT = 5_000
ENTITY_INDEX_RESULT_LIMIT = 100


@dataclass
class _Counter:
    names: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)
    records: int = 0
    san_bernardino: int = 0
    riverside: int = 0
    other: int = 0


def _target_county(value: str | None) -> str:
    normalized = (value or "").strip().casefold()
    if normalized.endswith(" county"):
        normalized = normalized[:-7]
    if normalized == "san bernardino":
        return "San Bernardino"
    if normalized == "riverside":
        return "Riverside"
    return ""


def build_entity_index(
    session: Session, *, kind: RecordSelection = "all", county: str = ""
) -> EntityIndexSnapshot:
    """Count exact-key co-occurrences, never inferred identities or distinct projects."""

    if kind not in {"all", "ceqa", "permit"}:
        raise ValueError("invalid source family")
    if county not in {"", "San Bernardino", "Riverside"}:
        raise ValueError("invalid county filter")
    records, total = read_project_page(
        session, kind=kind, query="", county=county,
        limit=ENTITY_INDEX_SCAN_LIMIT, offset=0,
    )
    counts: dict[str, _Counter] = {}
    for record in records:
        seen_in_record: set[str] = set()
        location = _target_county(record.county)
        for entity in record.entities:
            key = entity.entity_key
            if not key:
                continue
            counter = counts.setdefault(key, _Counter())
            if entity.name:
                counter.names.add(entity.name)
            if entity.role:
                counter.roles.add(entity.role)
            if key in seen_in_record:
                continue
            seen_in_record.add(key)
            counter.records += 1
            if location == "San Bernardino":
                counter.san_bernardino += 1
            elif location == "Riverside":
                counter.riverside += 1
            else:
                counter.other += 1

    ordered = sorted(counts.items(), key=lambda pair: (-pair[1].records, pair[0]))
    entries = [
        EntityIndexEntry(
            entity_key=key,
            source_claimed_names=sorted(counter.names)[:3],
            source_claimed_roles=sorted(counter.roles)[:4],
            matching_records_in_scan=counter.records,
            san_bernardino_records=counter.san_bernardino,
            riverside_records=counter.riverside,
            other_or_unknown_records=counter.other,
            appears_in_both_target_counties=bool(
                counter.san_bernardino and counter.riverside
            ),
        )
        for key, counter in ordered[:ENTITY_INDEX_RESULT_LIMIT]
    ]
    return EntityIndexSnapshot(
        selection=kind,
        county_filter=county,
        entries=entries,
        matching_source_records=total,
        scanned_source_records=len(records),
        distinct_keys_in_scan=len(counts),
        returned=len(entries),
        scan_limit=ENTITY_INDEX_SCAN_LIMIT,
        result_limit=ENTITY_INDEX_RESULT_LIMIT,
        source_scan_truncated=total > len(records),
        result_truncated=len(counts) > len(entries),
    )
