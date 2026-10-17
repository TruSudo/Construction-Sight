"""Phase 8 native read-only bridge to the preserved operator-source projections.

The legacy source database is selected explicitly. No database is initialized,
no remote collection occurs, and these source observations never become reviewed
investigations or commercial leads merely because they are displayed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.operator_parcel_candidates import inspect_parcel_candidates
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.operator_source_registry import build_operator_source_registry
from constructionsight.operator_source_review_queue import build_source_review_queue
from constructionsight.operator_source_revision import build_source_revision_snapshot
from constructionsight.operator_web import _parameters
from constructionsight.storage.operator_read_store import create_operator_read_engine

SOURCE_INSPECTION_ROUTES = frozenset(
    {
        "/api/source-registry",
        "/api/source-revision",
        "/api/source-review-queue",
        "/api/parcel-candidates",
        "/api/candidate-preview",
    }
)


def source_inspection(
    database: Path | None, *, route: str, query: str = ""
) -> dict[str, Any]:
    """Return existing governed operator projections without writing or acquiring data."""

    if route not in SOURCE_INSPECTION_ROUTES:
        raise ValueError("unsupported native source inspection route")
    if route in {"/api/source-registry", "/api/source-revision"}:
        if query:
            raise ValueError("source status inspection rejects query parameters")
        params = None
    else:
        params = _parameters(
            query,
            source_review_queue=route == "/api/source-review-queue",
            candidate=route in {"/api/parcel-candidates", "/api/candidate-preview"},
        )
    if database is None:
        return {
            "available": False,
            "configured": False,
            "read_only": True,
            "network_collection_enabled": False,
            "meaning": (
                "No existing operator source database was selected. Supply "
                "--operator-database to inspect retained source records."
            ),
        }
    if database.is_symlink() or not database.is_file():
        raise ValueError("operator source database must be an existing regular file, not a link")
    try:
        engine = create_operator_read_engine(database)
    except (SQLAlchemyError, OSError) as exc:
        raise ValueError("operator source database is unavailable or incompatible") from exc
    try:
        with Session(engine, autoflush=False) as session:
            if route == "/api/source-registry":
                result: dict[str, Any] = build_operator_source_registry(session).model_dump(
                    mode="json"
                )
            elif route == "/api/source-revision":
                result = build_source_revision_snapshot(session)
            elif route == "/api/source-review-queue":
                assert params is not None
                result = build_source_review_queue(
                    session,
                    kind=params.kind,
                    county=params.county,
                    query=params.query,
                    limit=params.limit,
                    offset=params.offset,
                ).model_dump(mode="json")
            else:
                assert params is not None and params.record_id is not None
                if params.kind == "all":
                    raise ValueError("exact CEQA or permit source record required")
                if route == "/api/parcel-candidates":
                    result = inspect_parcel_candidates(
                        session, kind=params.kind, record_id=params.record_id
                    ).model_dump(mode="json")
                else:
                    result = build_source_candidate_preview(
                        session, kind=params.kind, record_id=params.record_id
                    ).model_dump(mode="json")
            return {"available": True, **result}
    except SourceRecordNotFound as exc:
        raise ValueError("source record not found") from exc
    except SQLAlchemyError as exc:
        raise ValueError("operator source inspection failed") from exc
    finally:
        engine.dispose()
