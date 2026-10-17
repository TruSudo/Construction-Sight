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

from constructionsight.operator_capture_queue import (
    empty_operator_capture_queue,
    load_operator_capture_queue,
)
from constructionsight.operator_dashboard import (
    build_entity_neighborhood,
    build_geographic_footprint,
    build_historical_timeline,
    build_workflow_snapshot,
    build_workflow_status_summary,
)
from constructionsight.operator_entity_index import build_entity_index
from constructionsight.operator_parcel_candidates import inspect_parcel_candidates
from constructionsight.operator_results import build_result_ledger_snapshot
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.operator_source_registry import build_operator_source_registry
from constructionsight.operator_source_review_queue import build_source_review_queue
from constructionsight.operator_source_revision import build_source_revision_snapshot
from constructionsight.operator_watchlist import build_operator_watchlist_snapshot
from constructionsight.operator_web import _build_ceqanet_ingestion_payload, _parameters
from constructionsight.storage.operator_read_store import create_operator_read_engine

SOURCE_INSPECTION_ROUTES = frozenset(
    {
        "/api/source-registry",
        "/api/source-revision",
        "/api/source-review-queue",
        "/api/parcel-candidates",
        "/api/candidate-preview",
        "/api/source-watchlist",
        "/api/workflow-summary",
        "/api/workflows",
        "/api/results",
        "/api/source-entity-index",
        "/api/source-entity-neighborhood",
        "/api/source-timeline",
        "/api/source-footprint",
        "/api/source-capture-queue",
        "/api/source-ingestion-inbox",
    }
)


def source_inspection(
    database: Path | None,
    *,
    route: str,
    query: str = "",
    capture_queue: Path | None = None,
    ceqanet_listing: Path | None = None,
    ceqanet_review_queue: Path | None = None,
) -> dict[str, Any]:
    """Return existing governed operator projections without writing or acquiring data."""

    if route not in SOURCE_INSPECTION_ROUTES:
        raise ValueError("unsupported native source inspection route")
    if route in {
        "/api/source-registry", "/api/source-revision", "/api/source-watchlist",
        "/api/workflow-summary",
        "/api/source-capture-queue",
        "/api/source-ingestion-inbox",
    }:
        if query:
            raise ValueError("source status inspection rejects query parameters")
        params = None
    else:
        params = _parameters(
            query,
            source_review_queue=route == "/api/source-review-queue",
            workflow=route in {"/api/workflows", "/api/results"},
            results=route == "/api/results",
            candidate=route in {"/api/parcel-candidates", "/api/candidate-preview"},
            entity=route == "/api/source-entity-neighborhood",
            entity_index=route == "/api/source-entity-index",
            timeline=route == "/api/source-timeline",
            footprint=route == "/api/source-footprint",
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
            elif route == "/api/source-watchlist":
                result = build_operator_watchlist_snapshot(session)
            elif route == "/api/workflow-summary":
                result = build_workflow_status_summary(session)
            elif route == "/api/workflows":
                assert params is not None
                result = build_workflow_snapshot(
                    session, limit=params.limit, offset=params.offset
                )
            elif route == "/api/results":
                assert params is not None
                result = build_result_ledger_snapshot(
                    session, limit=params.limit, offset=params.offset
                )
            elif route == "/api/source-capture-queue":
                result = (
                    empty_operator_capture_queue()
                    if capture_queue is None else load_operator_capture_queue(capture_queue)
                )
            elif route == "/api/source-ingestion-inbox":
                result = _build_ceqanet_ingestion_payload(
                    session, listing_evidence=ceqanet_listing,
                    queue_evidence=ceqanet_review_queue,
                )
            elif route == "/api/source-entity-index":
                assert params is not None
                result = build_entity_index(
                    session, kind=params.kind, county=params.county,
                    role=params.role_filter,
                ).model_dump(mode="json")
            elif route == "/api/source-entity-neighborhood":
                assert params is not None and params.entity_key is not None
                result = build_entity_neighborhood(
                    session, entity_key=params.entity_key,
                    kind=params.kind, county=params.county,
                ).model_dump(mode="json")
            elif route == "/api/source-timeline":
                assert params is not None
                result = build_historical_timeline(
                    session, kind=params.kind, query=params.query,
                    county=params.county, entity_key=params.entity_key,
                ).model_dump(mode="json")
            elif route == "/api/source-footprint":
                assert params is not None
                result = build_geographic_footprint(
                    session, kind=params.kind, query=params.query, county=params.county,
                ).model_dump(mode="json")
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
