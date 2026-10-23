"""Read-only native bridge to original CEQAnet result-to-detail enrichment.

Accepts bounded, already-parsed offline snapshots; no HTTP, source promotion,
identity inference, retained-data mutation or commercial authorization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.adapters.ceqanet_detail_enrichment import (
    enrich_ceqanet_result_records,
)
from constructionsight.storage.domain_orm import CeqaDomainRecord
from constructionsight.storage.operator_read_store import create_operator_read_engine

_MAX_RESULTS = 50
_MAX_DETAILS = 50


def preview_original_ceqanet_enrichment(
    payload: dict[str, Any], database: Path | None = None,
) -> dict[str, Any]:
    """Run the retained offline enrichment algorithm on supplied parsed evidence."""
    if set(payload) != {"result_parse", "detail_parses"}:
        raise ValueError("exact original result-parse and detail-parses fields required")
    result = payload["result_parse"]
    details = payload["detail_parses"]
    if not isinstance(result, dict) or not isinstance(details, list):
        raise ValueError("original CEQAnet parse objects and detail list required")
    metadata = result.get("metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("schema_version") != "ceqanet_result_page_parse.v1"
    ):
        raise ValueError("original CEQAnet result parser schema required")
    records = result.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= _MAX_RESULTS:
        raise ValueError("between one and fifty parsed original result records required")
    if len(details) > _MAX_DETAILS:
        raise ValueError("at most fifty original detail parse objects allowed")
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("all original result records must be objects")

    known_sch: set[str] = set()
    for item in details:
        if not isinstance(item, dict):
            raise ValueError("each original detail parse must be an object")
        meta = item.get("metadata")
        detail = item.get("detail")
        if (
            not isinstance(meta, dict)
            or meta.get("schema_version") != "ceqanet_detail_page_parse.v1"
            or not isinstance(detail, dict)
        ):
            raise ValueError("original CEQAnet detail parser schema required")
        sch = detail.get("sch_number")
        if not isinstance(sch, str) or not sch.strip():
            raise ValueError("detail SCH identity is required to prevent ambiguous joins")
        if sch.strip() in known_sch:
            raise ValueError("duplicate detail SCH identity; reconcile offline first")
        known_sch.add(sch.strip())

    report = enrich_ceqanet_result_records(
        cast(list[dict[str, Any]], records),
        cast(list[dict[str, Any]], details),
    )
    return {
        "schema_version": "constructionsight.native-ceqanet-offline-enrichment/v1",
        "original_enrichment": report.to_dict(),
        "retained_source_matches": _exact_retained_source_matches(
            database, cast(list[dict[str, Any]], records)
        ),
        "read_only": True,
        "network_executed": False,
        "source_database_mutated": False,
        "investigation_queued": False,
        "source_claim_only": True,
        "commercial_authority_granted": False,
        "limitations": [
            "Parsed input is operator-supplied historical source evidence, not authenticated.",
            "The original enrichment joins detail by SCH, not project/site or contact identity.",
            "Missing or conflicting details do not establish independently verified facts.",
            "No collection, worker action, source promotion, outreach or bid is authorized.",
        ],
    }



def _exact_retained_source_matches(
    database: Path | None, records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compare untrusted parsed SCH labels with existing exact retained source keys.

    This is a separately observed local source inventory, not evidence authentication,
    an enrichment import, a project identity join or investigation authorization.
    Ambiguous SCH groups never provide an actionable record ID.
    """
    numbers: list[str | None] = []
    for record in records:
        raw = record.get("sch_number")
        if raw is None:
            numbers.append(None)
        elif not isinstance(raw, str) or len(raw) > 128:
            raise ValueError("original result SCH must be a bounded string or absent")
        else:
            numbers.append(raw.strip() or None)

    if database is None:
        return [
            {"sch_number": number, "status": "source_database_unavailable",
             "record_id": None, "retained_count": None}
            for number in numbers
        ]
    if database.is_symlink() or not database.is_file():
        raise ValueError("original operator database must be an existing regular file")
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            distinct = sorted({number for number in numbers if number is not None})
            groups: dict[str, tuple[int, str]] = {}
            if distinct:
                rows = session.execute(
                    select(
                        CeqaDomainRecord.state_clearinghouse_number,
                        func.count(),
                        func.min(CeqaDomainRecord.ceqa_key),
                    ).where(
                        CeqaDomainRecord.state_clearinghouse_number.in_(distinct)
                    ).group_by(CeqaDomainRecord.state_clearinghouse_number)
                ).all()
                groups = {
                    number: (count, key)
                    for number, count, key in rows
                    if isinstance(number, str) and isinstance(key, str)
                }
    except SQLAlchemyError as exc:
        raise ValueError("original retained CEQA source comparison is unavailable") from exc
    finally:
        engine.dispose()
    matches: list[dict[str, Any]] = []
    for number in numbers:
        count, key = groups.get(number, (0, "")) if number else (0, "")
        matches.append({
            "sch_number": number,
            "status": (
                "missing_sch" if number is None else
                "not_in_retained_source" if count == 0 else
                "unique_retained_sch" if count == 1 else
                "ambiguous_retained_sch"
            ),
            "record_id": key if count == 1 else None,
            "retained_count": count,
        })
    return matches
