"""Read existing CEQA/permit intelligence in the native SMARTS Command Center.

This module bridges *views*, not identities or storage. Source-family keys,
provenance, and limitations remain separate from SMARTS commercial leads.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from sqlalchemy.orm import Session

from constructionsight.operator_dashboard import build_dashboard_snapshot
from constructionsight.operator_entity_index import build_entity_index
from constructionsight.storage.operator_read_store import create_operator_read_engine


def source_intelligence_overview(database_path: Path | None) -> dict[str, Any]:
    """Return one bounded, read-only snapshot; never initialize a database.

    Without an explicitly selected database, counts are unknown (not zero).
    An invalid or incompatible selected database raises instead of fabricating
    an empty or complete inventory.
    """

    if database_path is None:
        return {
            "state": "unconfigured",
            "read_only": True,
            "records": None,
            "entities": None,
            "limitations": [
                "No existing CEQA/permit database was selected.",
                "SMARTS and government records have not been joined or verified.",
            ],
        }

    engine = create_operator_read_engine(database_path)
    try:
        with Session(engine, autoflush=False) as session:
            records = build_dashboard_snapshot(session, limit=25, offset=0)
            entities = build_entity_index(session)
            return {
                "state": "connected",
                "read_only": True,
                "records": records.model_dump(mode="json"),
                "entities": entities.model_dump(mode="json"),
                "limitations": [
                    "Government source records are not deduplicated SMARTS leads.",
                    "Matching names, coordinates or parcels do not verify site identity.",
                    "Displayed records and entity keys are bounded source-claimed views.",
                    "No outreach, source write, or bid is authorized by this view.",
                ],
            }
    finally:
        engine.dispose()


def _county(value: object) -> str:
    raw = str(value or "").strip().casefold()
    return raw.removesuffix(" county")


def _exact(value: object) -> str:
    """Conservative comparison: case and repeated whitespace only."""
    return re.sub(r"\\s+", " ", str(value or "").strip()).casefold()


def source_intelligence_site_picture(
    database_path: Path | None, smart_record: dict[str, Any]
) -> dict[str, Any]:
    """Review possible same-site CEQA/permit records without merging identities.

    Only an identical address or APN in the same county can flag a candidate.
    Source names, developer names and nearby coordinates are never enough.
    Source-page scanning is bounded and any incomplete scan is disclosed.
    """
    source_key = str(smart_record.get("source_key") or "")
    if not source_key:
        raise ValueError("SMARTS source identity is required")
    result: dict[str, Any] = {
        "schema_version": "constructionsight.unified-site-picture/v1",
        "smarts_source_key": source_key,
        "state": "unconfigured",
        "read_only": True,
        "match_verified": False,
        "commercial_authority_granted": False,
        "candidates": [],
        "records_scanned": 0,
        "matching_source_records": None,
        "scan_limit": 2000,
        "source_scan_truncated": False,
        "limitations": [
            "SMARTS and CEQA/permit records remain separately identified.",
            "Matching source-claimed identifiers are leads for human investigation, not proof.",
            "No sites, entities, stages, source facts or commercial statuses are merged.",
        ],
    }
    if database_path is None:
        result["limitations"].append("No read-only government records database configured.")
        return result
    county = _county(smart_record.get("SITE_COUNTY"))
    if county not in {"san bernardino", "riverside"}:
        result["state"] = "insufficient_identifiers"
        result["limitations"].append("SMARTS county is unavailable or out of supported scope.")
        return result
    county_filter = "San Bernardino" if county == "san bernardino" else "Riverside"
    address = _exact(smart_record.get("SITE_ADDRESS"))
    apn = _exact(smart_record.get("APN"))
    if not address and not apn:
        result["state"] = "insufficient_identifiers"
        result["limitations"].append("No exact source-claimed SMARTS address or APN.")
        return result
    engine = create_operator_read_engine(database_path)
    try:
        with Session(engine, autoflush=False) as session:
            page_size = 250
            offset = 0
            total = 0
            candidates: list[dict[str, Any]] = []
            while offset < result["scan_limit"]:
                page = build_dashboard_snapshot(
                    session, county=county_filter, limit=page_size, offset=offset
                )
                total = page.total
                for item in page.projects:
                    if _county(item.county) != county:
                        continue
                    signals: list[str] = []
                    if apn and _exact(item.apn) == apn:
                        signals.append("exact source-claimed APN and county")
                    if address and _exact(item.address) == address:
                        signals.append("exact source-claimed address and county")
                    if signals:
                        candidates.append({
                            "review_status": "possible_same_site_requires_review",
                            "signals": signals,
                            "source": item.model_dump(mode="json"),
                        })
                offset += page.returned
                if not page.has_more or page.returned == 0:
                    break
            result["matching_source_records"] = total
            result["records_scanned"] = offset
            result["source_scan_truncated"] = total > offset
            result["candidates"] = candidates[:25]
            result["candidate_count_in_scan"] = len(candidates)
            result["candidate_result_truncated"] = len(candidates) > 25
            result["state"] = "review_required" if candidates else "no_candidate_in_scan"
            if total > offset:
                result["limitations"].append(
                    "Scan is incomplete; unscanned records may contain further candidates."
                )
            if len(candidates) > 25:
                result["limitations"].append("Additional candidate records were omitted.")
            return result
    finally:
        engine.dispose()
