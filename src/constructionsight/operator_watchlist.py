"""Narrow persisted watchlist boundary for the local operator.

Source, lead, result, and collection records remain read-only.  This module opens
an existing SQLite database with a statement guard that permits mutations only
to the persisted intelligence watchlist table.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from sqlalchemy import Engine, create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from constructionsight.intelligence import WatchlistItem, WatchlistStatus
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.intelligence_orm import IntelligenceWatchlistRecord
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.watchlist_constants import (
    MAX_OPERATOR_WATCHLIST_ITEMS,
    OPERATOR_WORKSPACE_ID,
)

OperatorSourceKind = Literal["ceqa", "permit"]

_MUTATION_PREFIX = re.compile(
    r'^\s*(?:INSERT\s+INTO|UPDATE)\s+["\x60\[]?intelligence_watchlist_items(?:["\x60\]]|\s)',
    re.IGNORECASE,
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


def _guard_watchlist_only_mutation(
    _conn: Any,
    _cursor: Any,
    statement: str,
    _parameters: Any,
    _context: Any,
    _executemany: bool,
) -> None:
    """Reject every SQL mutation except insert/update of the watchlist table."""

    normalized = statement.lstrip()
    keyword = normalized.split(None, 1)[0].upper() if normalized else ""
    if keyword in {"SELECT", "PRAGMA"}:
        return
    if keyword in {"INSERT", "UPDATE"} and _MUTATION_PREFIX.match(normalized):
        return
    raise RuntimeError("operator write engine permits watchlist-table mutations only")


def create_operator_watchlist_engine(database_path: Path) -> Engine:
    """Open an existing SQLite database with watchlist-only mutation authority."""

    path = database_path.resolve(strict=True)
    if not path.is_file():
        raise ValueError("operator database must be an existing regular file")
    engine = create_engine(
        f"sqlite+pysqlite:///{path.as_uri()}?mode=rw&uri=true",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
    event.listen(engine, "before_cursor_execute", _guard_watchlist_only_mutation)
    try:
        with Session(engine, autoflush=False) as session:
            session.execute(select(IntelligenceWatchlistRecord).limit(0)).close()
    except Exception:
        engine.dispose()
        raise
    return engine


def validate_source_selection(*, kind: str, record_id: str) -> OperatorSourceKind:
    """Validate an exact source-family/source-record selection."""

    if kind not in {"ceqa", "permit"}:
        raise ValueError("watchlist requires an exact CEQA or permit source family")
    if (
        not record_id
        or len(record_id) > 255
        or record_id != record_id.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in record_id)
    ):
        raise ValueError("invalid watchlist source record identifier")
    return cast(OperatorSourceKind, kind)


def watchlist_item_id(*, kind: OperatorSourceKind, record_id: str) -> str:
    """Return a deterministic ID for one local workspace/source-record watch."""

    basis = json.dumps(
        [OPERATOR_WORKSPACE_ID, kind, record_id],
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "operator-watch:" + hashlib.sha256(basis).hexdigest()


def _source_record(session: Session, *, kind: OperatorSourceKind, record_id: str) -> Any:
    record = (
        CeqaStore(session).get(record_id)
        if kind == "ceqa"
        else PermitStore(session).get(record_id)
    )
    if record is None:
        raise LookupError("exact source record not found")
    return record


def add_source_watch(
    session: Session,
    *,
    kind: str,
    record_id: str,
) -> WatchlistItem:
    """Persist or reactivate one exact retained source-record watch."""

    source_kind = validate_source_selection(kind=kind, record_id=record_id)
    _source_record(session, kind=source_kind, record_id=record_id)
    item_id = watchlist_item_id(kind=source_kind, record_id=record_id)
    row = session.scalar(
        select(IntelligenceWatchlistRecord).where(
            IntelligenceWatchlistRecord.watchlist_item_id == item_id
        )
    )
    now = utc_now()
    created_at = now
    priority = 50
    notes = None
    if row is not None:
        existing = _validated_row_item(row)
        _require_index_identity(row, existing)
        if (
            existing.workspace_id != OPERATOR_WORKSPACE_ID
            or existing.target_type != f"source_record:{source_kind}"
            or existing.target_id != record_id
        ):
            raise ValueError("watchlist identity collision")
        created_at = existing.created_at
        priority = existing.priority
        notes = existing.notes

    item = WatchlistItem(
        watchlist_item_id=item_id,
        workspace_id=OPERATOR_WORKSPACE_ID,
        target_type=f"source_record:{source_kind}",
        target_id=record_id,
        status=WatchlistStatus.ACTIVE,
        priority=priority,
        alert_enabled=False,
        created_at=created_at,
        updated_at=now,
        notes=notes,
    )
    IntelligenceStore(session).upsert_watchlist_item(item)
    return item


def archive_source_watch(
    session: Session,
    *,
    kind: str,
    record_id: str,
) -> WatchlistItem:
    """Archive one exact watchlist item without deleting retained history."""

    source_kind = validate_source_selection(kind=kind, record_id=record_id)
    item_id = watchlist_item_id(kind=source_kind, record_id=record_id)
    row = session.scalar(
        select(IntelligenceWatchlistRecord).where(
            IntelligenceWatchlistRecord.watchlist_item_id == item_id
        )
    )
    if row is None:
        raise LookupError("watchlist item not found")
    existing = _validated_row_item(row)
    _require_index_identity(row, existing)
    if (
        existing.workspace_id != OPERATOR_WORKSPACE_ID
        or existing.target_type != f"source_record:{source_kind}"
        or existing.target_id != record_id
    ):
        raise ValueError("watchlist identity collision")
    archived = existing.model_copy(
        update={
            "status": WatchlistStatus.ARCHIVED,
            "alert_enabled": False,
            "updated_at": utc_now(),
        }
    )
    IntelligenceStore(session).upsert_watchlist_item(archived)
    return archived


def build_operator_watchlist_snapshot(session: Session) -> dict[str, object]:
    """Return current persisted watches with source labels re-read from canonical rows."""

    rows = session.scalars(
        select(IntelligenceWatchlistRecord)
        .where(IntelligenceWatchlistRecord.workspace_id == OPERATOR_WORKSPACE_ID)
        .order_by(IntelligenceWatchlistRecord.id.desc())
        .limit(MAX_OPERATOR_WATCHLIST_ITEMS + 1)
    ).all()
    if len(rows) > MAX_OPERATOR_WATCHLIST_ITEMS:
        raise ValueError("operator watchlist exceeds bounded inspection limit")

    items: list[dict[str, object]] = []
    for row in rows:
        item = _validated_row_item(row)
        _require_index_identity(row, item)
        if item.status is WatchlistStatus.ARCHIVED:
            continue
        source_kind = _kind_from_target_type(item.target_type)
        source = _source_record_or_none(session, kind=source_kind, record_id=item.target_id)
        title = (
            source.title
            if source_kind == "ceqa" and source is not None
            else source.permit_number
            if source is not None
            else None
        )
        county = source.county if source is not None else None
        items.append(
            {
                "watchlist_item_id": item.watchlist_item_id,
                "record_kind": source_kind,
                "record_id": item.target_id,
                "title": title,
                "county": county,
                "status": item.status.value,
                "priority": item.priority,
                "alert_enabled": False,
                "change_pending": item.status is WatchlistStatus.TRIGGERED,
                "target_available": source is not None,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
        )

    return {
        "schema_version": "operator_watchlist.v1",
        "workspace_id": OPERATOR_WORKSPACE_ID,
        "items": items,
        "total": len(items),
        "persisted_locally": True,
        "source_records_read_only": True,
        "source_monitoring_enabled": False,
        "retained_source_change_detection_enabled": True,
        "remote_source_polling_enabled": False,
        "notification_delivery_enabled": False,
        "commercial_actions_authorized": False,
        "limitations": [
            "Retained normalized source changes automatically trigger matching active watches.",
            "Watchlist membership does not start source polling or remote collection.",
            "No reminder or notification delivery is enabled.",
            "Watchlist membership does not establish project readiness or authorize outreach or bids.",
        ],
    }


def _validated_row_item(row: IntelligenceWatchlistRecord) -> WatchlistItem:
    try:
        return WatchlistItem.model_validate_json(row.payload_json)
    except ValueError as exc:
        raise ValueError("invalid persisted watchlist payload") from exc


def _require_index_identity(row: IntelligenceWatchlistRecord, item: WatchlistItem) -> None:
    target_type = (
        item.target_type.value
        if hasattr(item.target_type, "value")
        else str(item.target_type)
    )
    expected = (
        item.watchlist_item_id,
        item.workspace_id,
        target_type,
        item.target_id,
        item.status.value,
        item.priority,
    )
    actual = (
        row.watchlist_item_id,
        row.workspace_id,
        row.target_type,
        row.target_id,
        row.status,
        row.priority,
    )
    if actual != expected:
        raise ValueError("watchlist indexed fields disagree with retained payload")


def _kind_from_target_type(target_type: object) -> OperatorSourceKind:
    value = target_type.value if hasattr(target_type, "value") else str(target_type)
    if value == "source_record:ceqa":
        return "ceqa"
    if value == "source_record:permit":
        return "permit"
    raise ValueError("operator watchlist contains unsupported target type")


def _source_record_or_none(
    session: Session,
    *,
    kind: OperatorSourceKind,
    record_id: str,
) -> Any | None:
    return (
        CeqaStore(session).get(record_id)
        if kind == "ceqa"
        else PermitStore(session).get(record_id)
    )
