"""Read-only Command Center reuse of original offline saved-snapshot chain builder.

One in-memory operator review, not a download, persistence write, promotion
or source authentication. Both CLI and native call the same original composer.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

import typer

from constructionsight.ceqanet_chain_cli import build_chain_report_from_saved_executions

_MAX_DETAIL_EXECUTIONS = 25
_MAX_RESULT_RECORDS = 50
_MAX_RESPONSE_BYTES = 2_000_000


def original_offline_chain_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Preview a bounded original chain report from already-saved execution JSON."""
    if set(payload) != {
        "listing_execution", "detail_executions", "listing_snapshot_index",
    }:
        raise ValueError("exact saved listing, details and snapshot index required")
    listing = payload["listing_execution"]
    details = payload["detail_executions"]
    index = payload["listing_snapshot_index"]
    if not isinstance(listing, dict):
        raise ValueError("saved listing execution must be a JSON object")
    if not isinstance(details, list) or len(details) > _MAX_DETAIL_EXECUTIONS:
        raise ValueError("at most twenty-five saved original detail executions allowed")
    if any(not isinstance(detail, dict) for detail in details):
        raise ValueError("every saved detail execution must be an object")
    if type(index) is not int or not 0 <= index < 25:
        raise ValueError("saved listing snapshot index must be an integer from 0 to 24")

    detail_labels = [
        f"native-offline-detail-execution-{number}"
        for number in range(len(details))
    ]
    try:
        report = build_chain_report_from_saved_executions(
            cast(dict[str, Any], listing),
            cast(list[dict[str, Any]], details),
            listing_snapshot_index=index,
            listing_label="native-offline-listing-execution",
            detail_labels=detail_labels,
        )
    except typer.BadParameter as exc:
        raise ValueError(f"saved original execution is invalid: {exc}") from exc

    metadata = report.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("original CEQAnet chain metadata is missing")
    count = metadata.get("result_record_count")
    if type(count) is not int or not 0 <= count <= _MAX_RESULT_RECORDS:
        raise ValueError("original chain result exceeds fifty-record native review bound")
    if len(json.dumps(report, allow_nan=False).encode("utf-8")) > _MAX_RESPONSE_BYTES:
        raise ValueError("original chain report exceeds two-megabyte review bound")
    inputs = [listing, *details]
    digests = [
        hashlib.sha256(
            json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            .encode("utf-8")
        ).hexdigest()
        for item in inputs
    ]
    return {
        "schema_version": "constructionsight.original-ceqanet-offline-chain-preview/v1",
        "original_chain_report": report,
        "input_canonical_json_sha256": {
            "listing_execution": digests[0],
            "detail_executions": digests[1:],
        },
        "read_only": True,
        "network_executed": False,
        "source_database_mutated": False,
        "chain_report_retained": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Original offline saved-execution chain builder, never a newly "
            "authenticated public source, current project, retained chain report, "
            "investigation approval or commercial authorization."
        ),
    }
