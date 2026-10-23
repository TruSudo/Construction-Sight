"""Read-only native bridge to original CEQAnet result-to-detail enrichment.

Accepts bounded, already-parsed offline snapshots; no HTTP, source promotion,
identity inference, retained-data mutation or commercial authorization.
"""

from __future__ import annotations

from typing import Any, cast

from constructionsight.adapters.ceqanet_detail_enrichment import (
    enrich_ceqanet_result_records,
)

_MAX_RESULTS = 50
_MAX_DETAILS = 50


def preview_original_ceqanet_enrichment(payload: dict[str, Any]) -> dict[str, Any]:
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
