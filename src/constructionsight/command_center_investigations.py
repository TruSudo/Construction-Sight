"""Read-only bridge from the native Command Center to the existing investigation store.

The worker owns all evidence, identity decisions and revisions. This adapter
does not initialize the database, invent map points or apply commercial scores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.storage.database import (
    managed_session,
    prepare_private_database,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.operator_read_store import create_operator_read_engine


def investigation_view(
    directory: Path,
    *,
    investigation_id: str | None = None,
    after: str | None = None,
    revision_only: bool = False,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Query authoritative state with an owner-only, existing SQLite mode=ro connection."""
    if investigation_id is not None and (not investigation_id or len(investigation_id) > 255):
        raise ValueError("invalid investigation identifier")
    if investigation_id is not None and after is not None:
        raise ValueError("dossier requests cannot carry inventory cursors")
    if investigation_id is not None and filters:
        raise ValueError("dossier requests cannot carry inventory filters")
    if revision_only and (investigation_id is not None or after is not None or filters):
        raise ValueError("revision requests cannot carry filters, identity or cursor")
    database = directory / "investigations.sqlite3"
    # Missing worker initialization is not evidence that no investigations exist.
    if not database.exists() and not database.is_symlink():
        if investigation_id is not None:
            raise ValueError("investigation store has not been initialized")
        return {
            "schema_version": "constructionsight.investigation-inventory/v1",
            "available": False,
            "event_cursor": None,
            "total": 0,
            "rows": [],
            "has_more": False,
            "next_cursor": None,
            "mapped_on_page": 0,
            "unmapped_on_page": [],
        }
    prepare_private_database(database, create=False)
    try:
        engine = create_operator_read_engine(database)
    except (OSError, SQLAlchemyError) as exc:
        raise ValueError("investigation store is unavailable or unreadable") from exc
    try:
        with managed_session(session_factory(engine)) as session:
            store = IntelligenceStore(session)
            if revision_only:
                return {"available": True, "event_cursor": store.runtime_event_cursor()}
            service = InvestigationQueryService(store)
            if investigation_id is not None:
                return service.dossier(investigation_id, evidence_limit=100)
            options = filters or {}
            result = service.inventory(
                after=after,
                limit=50,
                text=options.get("text", ""),
                county=options.get("county", ""),
                city=options.get("city", ""),
                source_family=options.get("source_family", ""),
                location=options.get("location", ""),
            )
            return {"available": True, **result}
    except SQLAlchemyError as exc:
        raise ValueError("investigation store query failed") from exc
    finally:
        engine.dispose()
