"""Native read-only access to the original retained upstream record inspector.

Reuse the original list/detail projections and the explicitly selected existing
operator database. Inspection grants no investigation, source or commercial action.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    _FILTER_SUPPORT,
    get_upstream_operator_record,
    list_upstream_operator_records,
)

_FILTERS = frozenset({"status", "source_key", "source_record_id", "site_key", "apn", "county"})
_MAX_RESPONSE_BYTES = 2_000_000


def inspect_original_upstream_records(
    database: Path | None, *, query: str = "",
) -> dict[str, Any]:
    """Catalog, bounded original list, or exact original record; never initialize DBs."""
    if len(query) > 5000:
        raise ValueError("upstream inspection query exceeds its bound")
    try:
        values = parse_qs(query, keep_blank_values=True, strict_parsing=True, max_num_fields=9)
    except ValueError as exc:
        raise ValueError("invalid upstream inspection query") from exc
    if set(values) - (_FILTERS | {"kind", "record_id", "limit"}):
        raise ValueError("unsupported upstream inspection parameter")
    if any(
        len(items) != 1 or not 1 <= len(items[0]) <= 512
        or any(ord(char) < 32 or ord(char) == 127 for char in items[0])
        for items in values.values()
    ):
        raise ValueError("one nonempty bounded value per upstream parameter required")
    params = {key: items[0] for key, items in values.items()}
    if params and "kind" not in params:
        raise ValueError("select one original upstream record family")
    kind = UpstreamOperatorRecordKind(params["kind"]) if params else None
    record_id = params.get("record_id")
    if record_id is not None and set(params) != {"kind", "record_id"}:
        raise ValueError("exact upstream detail rejects list filters and limits")
    if kind is not None and (set(params) & _FILTERS) - _FILTER_SUPPORT[kind]:
        raise ValueError("selected upstream family does not support that filter")
    raw_limit = params.get("limit", "25")
    if not raw_limit.isascii() or not raw_limit.isdecimal():
        raise ValueError("upstream list limit must be an integer between 1 and 1000")
    limit = int(raw_limit)
    if str(limit) != raw_limit or not 1 <= limit <= 1000:
        raise ValueError("upstream list limit must be an integer between 1 and 1000")
    result: dict[str, Any] = {
        "schema_version": "constructionsight.original-upstream-inspection/v1",
        "available": database is not None,
        "configured": database is not None,
        "mode": "catalog" if kind is None else "detail" if record_id else "list",
        "read_only": True,
        "network_executed": False,
        "source_database_mutated": False,
        "source_claim_only": True,
        "investigation_queued": False,
        "commercial_authority_granted": False,
        "record_families": [
            {"kind": item.value, "supported_filters": sorted(_FILTER_SUPPORT[item])}
            for item in UpstreamOperatorRecordKind
        ],
        "limitations": [
            "Original retained upstream projections; not independent verification.",
            "A stored resolution, status or confidence is a historical source claim.",
            "No project match, worker replay, collection, outreach or bid is authorized.",
        ],
    }
    if database is None:
        result["meaning"] = "No existing operator source database was selected."
        return result
    if database.is_symlink() or not database.is_file():
        raise ValueError("operator source database must be an existing regular file, not a link")
    try:
        engine = create_operator_read_engine(database)
        try:
            with Session(engine, autoflush=False) as session:
                if kind is not None:
                    result["record_kind"] = kind.value
                    if record_id is not None:
                        record = get_upstream_operator_record(session, kind, record_id)
                        result["record"] = None if record is None else record.to_dict()
                        result["found"] = record is not None
                    else:
                        records = list_upstream_operator_records(
                            session, kind, limit=limit,
                            **{key: value for key, value in params.items() if key in _FILTERS},
                        )
                        result["records"] = [record.to_dict() for record in records]
                        result["returned_count"] = len(records)
                        result["limit"] = limit
                        result["possibly_truncated"] = len(records) == limit
                        result["limitations"].append(
                            "Newest bounded list only, not a total count. Narrow exact "
                            "filters or inspect an exact record ID for older records."
                        )
        finally:
            engine.dispose()
    except (SQLAlchemyError, OSError, TypeError, KeyError) as exc:
        raise ValueError("original upstream evidence is unavailable or incompatible") from exc
    if len(json.dumps(result, allow_nan=False).encode("utf-8")) > _MAX_RESPONSE_BYTES:
        raise ValueError("upstream result exceeds 2 MB; narrow filters or inspect an exact ID")
    return result
