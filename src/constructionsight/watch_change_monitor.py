"""Trusted watch-change detection over retained normalized source history."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.intelligence import (
    RuntimeEvent,
    RuntimeEventSeverity,
    RuntimeEventType,
    WatchlistItem,
    WatchlistStatus,
)
from constructionsight.storage.intelligence_orm import IntelligenceRuntimeEventRecord
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.watchlist_constants import (
    MAX_OPERATOR_WATCHLIST_ITEMS,
    OPERATOR_WORKSPACE_ID,
)

MAX_WATCH_CHANGE_EVENTS = 10_000


@dataclass(frozen=True)
class WatchChangeScanReport:
    """Summary of one bounded watch-change scan."""

    scanned_watches: int
    scanned_change_events: int
    triggered_watch_ids: tuple[str, ...]
    trigger_event_ids: tuple[str, ...]


def trigger_watches_for_source_change(
    session: Session,
    source_event: RuntimeEvent,
    *,
    workspace_id: str = OPERATOR_WORKSPACE_ID,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Trigger active exact-source watches for one retained change event."""

    if source_event.event_type is not RuntimeEventType.SOURCE_RECORD_CHANGED:
        return (), ()

    store = IntelligenceStore(session)
    watches = store.list_watchlist_items(
        workspace_id=workspace_id,
        limit=MAX_OPERATOR_WATCHLIST_ITEMS + 1,
    )
    if len(watches) > MAX_OPERATOR_WATCHLIST_ITEMS:
        raise ValueError("watch change scan exceeds bounded watchlist limit")

    triggered_watch_ids: list[str] = []
    trigger_event_ids: list[str] = []
    for watch in watches:
        if watch.status is not WatchlistStatus.ACTIVE:
            continue
        source_ref = _source_ref(watch)
        if source_ref is None or source_ref not in source_event.source_record_refs:
            continue
        if source_event.created_at <= watch.updated_at:
            continue

        now = datetime.now(UTC)
        triggered = watch.model_copy(
            update={
                "status": WatchlistStatus.TRIGGERED,
                "updated_at": now,
            }
        )
        store.upsert_watchlist_item(triggered)
        attention = _attention_event(triggered, source_event, created_at=now)
        store.add_runtime_event(attention)
        triggered_watch_ids.append(triggered.watchlist_item_id)
        trigger_event_ids.append(attention.event_id)

    return tuple(triggered_watch_ids), tuple(trigger_event_ids)


def scan_watched_source_changes(
    session: Session,
    *,
    workspace_id: str = OPERATOR_WORKSPACE_ID,
    max_events: int = MAX_WATCH_CHANGE_EVENTS,
) -> WatchChangeScanReport:
    """Recover watch triggers from bounded retained source-change history."""

    if isinstance(max_events, bool) or not isinstance(max_events, int) or max_events < 1:
        raise ValueError("watch change scan limit must be a positive integer")

    changed_rows = session.scalars(
        select(IntelligenceRuntimeEventRecord)
        .where(
            IntelligenceRuntimeEventRecord.event_type
            == RuntimeEventType.SOURCE_RECORD_CHANGED.value
        )
        .order_by(IntelligenceRuntimeEventRecord.id.desc())
        .limit(max_events + 1)
    ).all()
    if len(changed_rows) > max_events:
        raise ValueError("watch change event history exceeds bounded scan limit")

    triggered_watch_ids: list[str] = []
    trigger_event_ids: list[str] = []
    for row in reversed(changed_rows):
        source_event = RuntimeEvent.model_validate_json(row.payload_json)
        watch_ids, event_ids = trigger_watches_for_source_change(
            session,
            source_event,
            workspace_id=workspace_id,
        )
        triggered_watch_ids.extend(watch_ids)
        trigger_event_ids.extend(event_ids)

    store = IntelligenceStore(session)
    watches = store.list_watchlist_items(
        workspace_id=workspace_id,
        limit=MAX_OPERATOR_WATCHLIST_ITEMS + 1,
    )
    if len(watches) > MAX_OPERATOR_WATCHLIST_ITEMS:
        raise ValueError("watch change scan exceeds bounded watchlist limit")

    return WatchChangeScanReport(
        scanned_watches=len(watches),
        scanned_change_events=len(changed_rows),
        triggered_watch_ids=tuple(triggered_watch_ids),
        trigger_event_ids=tuple(trigger_event_ids),
    )


def _source_ref(watch: WatchlistItem) -> str | None:
    """Return the normalized-domain event reference for a supported watch."""

    target_type = (
        watch.target_type.value
        if hasattr(watch.target_type, "value")
        else str(watch.target_type)
    )
    if target_type == "source_record:ceqa":
        return f"ceqa:{watch.target_id}"
    if target_type == "source_record:permit":
        return f"permit:{watch.target_id}"
    return None


def _attention_event(
    watch: WatchlistItem,
    source_event: RuntimeEvent,
    *,
    created_at: datetime,
) -> RuntimeEvent:
    """Build one deterministic user-attention event for a source change."""

    payload = {
        "watchlist_item_id": watch.watchlist_item_id,
        "workspace_id": watch.workspace_id,
        "target_type": (
            watch.target_type.value
            if hasattr(watch.target_type, "value")
            else str(watch.target_type)
        ),
        "target_id": watch.target_id,
        "source_change_event_id": source_event.event_id,
    }
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    event_id = "event:watch-trigger:" + hashlib.sha256(canonical).hexdigest()
    return RuntimeEvent(
        event_id=event_id,
        event_type=RuntimeEventType.SOURCE_RECORD_CHANGED,
        severity=RuntimeEventSeverity.MEDIUM,
        created_at=created_at,
        source_service="watchlist_change_monitor",
        causation_id=source_event.event_id,
        source_record_refs=list(source_event.source_record_refs),
        payload=payload,
        message="A watched retained source record changed.",
        requires_user_attention=True,
    )
