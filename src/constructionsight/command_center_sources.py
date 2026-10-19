"""Phase 8 native read-only bridge to the preserved operator-source projections.

The legacy source database is selected explicitly. No database is initialized,
no remote collection occurs, and these source observations never become reviewed
investigations or commercial leads merely because they are displayed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.adapters import default_adapter_family_specs

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
from constructionsight.operator_source_aliases import LoadedSourceAttributionAliases
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.operator_source_registry import build_operator_source_registry
from constructionsight.operator_source_review_queue import build_source_review_queue
from constructionsight.operator_source_revision import build_source_revision_snapshot
from constructionsight.operator_watchlist import (
    add_source_watch,
    archive_source_watch,
    build_operator_watchlist_snapshot,
    create_operator_watchlist_engine,
    validate_source_selection,
)
from constructionsight.operator_web import (
    _build_ceqanet_ingestion_payload,
    _parameters,
    _parse_smarts_parcel_query,
    _validate_smarts_change_query,
)
from constructionsight.smarts_operator_status import build_smarts_operator_status
from constructionsight.smarts_parcel_review import inspect_smarts_parcel_candidates
from constructionsight.smarts_snapshot_history import review_snapshot_changes
from constructionsight.source_status_report import build_source_status_report
from constructionsight.source_verification_evidence_service import (
    build_source_verification_evidence_package,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.orm import SourceRecord
from constructionsight.storage.parcel_site_orm import ParcelArcGISBoundedProofBundleRow
from constructionsight.storage.parcel_source_acquisition_bundle_store import (
    load_arcgis_bounded_proof_bundles,
)
from constructionsight.storage.source_registry import SourceRegistryStore

SOURCE_INSPECTION_ROUTES = frozenset(
    {
        "/api/source-registry",
        "/api/source-offline-audit",
        "/api/source-revision",
        "/api/source-review-queue",
        "/api/parcel-candidates",
        "/api/candidate-preview",
        "/api/source-watchlist",
        "/api/source-parcel-proofs",
        "/api/workflow-summary",
        "/api/workflows",
        "/api/results",
        "/api/source-entity-index",
        "/api/source-entity-neighborhood",
        "/api/source-timeline",
        "/api/source-footprint",
        "/api/source-capture-queue",
        "/api/source-ingestion-inbox",
        "/api/source-smarts-status",
        "/api/source-smarts-changes",
        "/api/source-smarts-parcel-candidates",
    }
)


def retained_watch_notifications(database: Path | None) -> list[dict[str, Any]]:
    """Project existing triggered source watches into the local notification inbox.

    The original validated watch snapshot owns trigger/rearm/archive semantics.
    Reading it starts no polling and mutates neither the source nor the watch.
    Native read receipts are kept separately by command_center_state.
    """
    snapshot = source_inspection(database, route="/api/source-watchlist")
    if not snapshot["available"]:
        return []
    notices = []
    for watch in snapshot["items"]:
        if not watch["change_pending"]:
            continue
        identity = json.dumps(
            [watch["watchlist_item_id"], watch["updated_at"]],
            separators=(",", ":"), ensure_ascii=False,
        ).encode()
        notices.append({
            "id": "source-watch:" + hashlib.sha256(identity).hexdigest(),
            "record_kind": watch["record_kind"],
            "record_id": watch["record_id"],
            "watchlist_item_id": watch["watchlist_item_id"],
            "message": "Watched retained source changed: " + str(
                watch["title"] or watch["record_id"]
            ),
            "county": watch["county"],
            "city": None,
            "source_claim_only": True,
        })
    return notices


def source_inspection(
    database: Path | None,
    *,
    route: str,
    query: str = "",
    capture_queue: Path | None = None,
    ceqanet_listing: Path | None = None,
    ceqanet_review_queue: Path | None = None,
    smarts_journal: Path | None = None,
    smarts_history: Path | None = None,
    source_aliases: LoadedSourceAttributionAliases | None = None,
) -> dict[str, Any]:
    """Return existing governed operator projections without writing or acquiring data."""

    if route not in SOURCE_INSPECTION_ROUTES:
        raise ValueError("unsupported native source inspection route")
    if route in {
        "/api/source-registry", "/api/source-offline-audit",
        "/api/source-revision", "/api/source-watchlist",
        "/api/source-parcel-proofs", "/api/workflow-summary",
        "/api/source-capture-queue",
        "/api/source-ingestion-inbox",
        "/api/source-smarts-status",
    }:
        if query:
            raise ValueError("source status inspection rejects query parameters")
        params = None
    elif route == "/api/source-smarts-changes":
        _validate_smarts_change_query(query)
        params = _parameters(query, source_review_queue=True)
    elif route == "/api/source-smarts-parcel-candidates":
        snapshot_id, source_key = _parse_smarts_parcel_query(query)
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
    if (
        route in {"/api/source-smarts-changes", "/api/source-smarts-parcel-candidates"}
        and smarts_history is None
    ):
        return {
            "available": False, "configured": False, "read_only": True,
            "network_collection_enabled": False,
            "meaning": "No existing private SMARTS snapshot history was configured.",
        }
    if database.is_symlink() or not database.is_file():
        raise ValueError("operator source database must be an existing regular file, not a link")
    try:
        engine = create_operator_read_engine(database)
    except (SQLAlchemyError, OSError) as exc:
        raise ValueError("operator source database is unavailable or incompatible") from exc
    try:
        with Session(engine, autoflush=False) as session:
            if route == "/api/source-offline-audit":
                # Reuse original CLI audit builders against the actual retained
                # registry. No HTTP probe, source promotion, acquisition or write.
                count = session.scalar(select(func.count()).select_from(SourceRecord)) or 0
                if count > 2000:
                    raise ValueError("original registry exceeds 2000-item offline audit bound")
                sources = SourceRegistryStore(session).list_sources()
                if len(sources) != count:
                    raise ValueError("original source registry changed during audit")
                adapters = default_adapter_family_specs()
                status = build_source_status_report(sources, adapters)
                evidence = build_source_verification_evidence_package(
                    sources, adapters, check_http=False,
                )
                result = {
                    "schema_version": "constructionsight.original-offline-source-audit/v1",
                    "source_count": count,
                    "original_status_report": status.to_dict(),
                    "original_evidence_package": evidence.to_dict(),
                    "network_executed": False,
                    "http_checked": False,
                    "source_database_mutated": False,
                    "read_only": True,
                    "source_promotion_authorized": False,
                    "source_claim_only": True,
                    "limitations": [
                        "Offline report does not establish current endpoint reachability.",
                        "Original verification labels are reproduced, not revalidated.",
                        "No source, parcel, identity or commercial authority is promoted.",
                    ],
                }
            elif route == "/api/source-registry":
                result: dict[str, Any] = build_operator_source_registry(
                    session, source_aliases=source_aliases,
                ).model_dump(
                    mode="json"
                )
            elif route == "/api/source-revision":
                result = build_source_revision_snapshot(session)
            elif route == "/api/source-watchlist":
                result = build_operator_watchlist_snapshot(session)
            elif route == "/api/source-parcel-proofs":
                # The original persisted proof chain validates every indexed bundle
                # against its payload and all retained source dependencies. Avoid an
                # unbounded decode and refuse to hide any surplus records.
                total = session.scalar(
                    select(func.count()).select_from(ParcelArcGISBoundedProofBundleRow)
                ) or 0
                if total > 50:
                    raise ValueError("original ArcGIS bounded proof inventory exceeds 50 items")
                bundles = load_arcgis_bounded_proof_bundles(session)
                if len(bundles) != total:
                    raise ValueError("original ArcGIS proof inventory changed during read")
                result = {
                    "schema_version": "constructionsight.retained-arcgis-proofs/v1",
                    "total": total,
                    "bundles": [bundle.to_dict() for bundle in bundles],
                    "read_only": True,
                    "proof_chain_validated": True,
                    "network_collection_enabled": False,
                    "identity_independently_verified": False,
                    "bulk_acquisition_authorized": False,
                    "commercial_actions_authorized": False,
                    "meaning": (
                        "Original bounded ArcGIS proof chain only; a proof does not "
                        "establish countywide acquisition, parcel import, a common "
                        "construction project, mapped location, or commercial authority."
                    ),
                }
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
            elif route == "/api/source-smarts-status":
                result = build_smarts_operator_status(smarts_journal, smarts_history)
            elif route == "/api/source-smarts-changes":
                assert params is not None
                result = review_snapshot_changes(
                    smarts_history, county=params.county, limit=params.limit,
                    offset=params.offset,
                )
            elif route == "/api/source-smarts-parcel-candidates":
                result = inspect_smarts_parcel_candidates(
                    session, history_path=smarts_history,
                    snapshot_id=snapshot_id, source_key=source_key,
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


def source_watch_action(
    database: Path | None, *, action: str, kind: str, record_id: str,
) -> dict[str, Any]:
    """Apply only the original watchlist-table mutation to an existing source identity.

    The local server enforces Origin, Host, an exact request object, and the
    maintenance lock. The original guard confines every SQL write to the local
    intelligence watchlist table; source, investigative and commercial facts
    remain untouched. No background monitoring or communications are started.
    """

    if action not in {"add", "archive"}:
        raise ValueError("invalid source watch action")
    validate_source_selection(kind=kind, record_id=record_id)
    if database is None:
        raise ValueError("no existing operator source database is configured")
    if database.is_symlink() or not database.is_file():
        raise ValueError("operator source database must be an existing regular file")
    try:
        engine = create_operator_watchlist_engine(database)
    except (SQLAlchemyError, OSError, ValueError) as exc:
        raise ValueError("source watchlist storage is unavailable") from exc
    try:
        with Session(engine, autoflush=False) as session, session.begin():
            if action == "add":
                add_source_watch(session, kind=kind, record_id=record_id)
            else:
                archive_source_watch(session, kind=kind, record_id=record_id)
            result = build_operator_watchlist_snapshot(session)
        return {"available": True, "mutation": action, **result}
    except LookupError as exc:
        raise ValueError("selected source or watch record was not found") from exc
    except (SQLAlchemyError, RuntimeError) as exc:
        raise ValueError("source watchlist operation failed") from exc
    finally:
        engine.dispose()
