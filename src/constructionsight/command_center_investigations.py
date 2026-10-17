"""Native queries and explicit local reviews over the existing investigation store.

Queries remain read-only. Review writes use the established evidence-bound service;
this bridge never initializes the database, invents map points or applies commercial scores.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.investigation_review_service import InvestigationReviewService
from constructionsight.storage.database import (
    create_private_database_engine,
    managed_session,
    prepare_private_database,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.operator_read_store import create_operator_read_engine


class AssociationReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    relationship_id: str = Field(min_length=1, max_length=255)
    expected_identity: str = Field(min_length=1, max_length=255)
    decision: Literal["associate", "reject"]
    target_id: str | None = Field(default=None, min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=4000)
    caller_confirmation: bool
    operator_id: str | None = Field(default=None, min_length=1, max_length=255)


def investigation_review_preview(directory: Path, relationship_id: str) -> dict[str, Any]:
    """Preview an existing candidate and evidence in a read-only SQLite snapshot."""
    if not relationship_id or len(relationship_id) > 255:
        raise ValueError("invalid candidate relationship identifier")
    database = prepare_private_database(directory / "investigations.sqlite3", create=False)
    engine = create_operator_read_engine(database)
    try:
        return InvestigationReviewService(engine).preview(relationship_id)
    except SQLAlchemyError as exc:
        raise ValueError("investigation review preview is unavailable") from exc
    finally:
        engine.dispose()


def apply_investigation_review(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Use the existing scope-bound local review effect; never initialize a store."""
    request = AssociationReviewRequest.model_validate(payload)
    if not request.caller_confirmation:
        raise ValueError("explicit confirmation is required for an association review")
    database = prepare_private_database(directory / "investigations.sqlite3", create=False)
    engine = create_private_database_engine(database, create=False)
    try:
        return InvestigationReviewService(engine).review(**request.model_dump())
    except AuthorizationDeniedError as exc:
        raise ValueError(str(exc)) from exc
    except SQLAlchemyError as exc:
        raise ValueError("investigation review could not be committed; reload the preview") from exc
    finally:
        engine.dispose()


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
