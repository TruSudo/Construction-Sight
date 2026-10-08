"""Trusted watch-change detection over retained normalized source history."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.intelligence import RuntimeEventType
from constructionsight.storage.intelligence_orm import IntelligenceRuntimeEventRecord
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.watch_change_store import trigger_watches_for_source_change
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


