"""Storage-layer watch triggering for retained source-change events."""

from __future__ import annotations

import hashlib
import json
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
from constructionsight.storage.intelligence_orm import IntelligenceWatchlistRecord
from constructionsight.storage.intelligence_store import IntelligenceStore


def trigger_watches_for_source_change(
    session: Session,
    source_event: RuntimeEvent,
    *,
    workspace_id: str | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Trigger matching active watches for one retained source-change event."""

    if source_event.event_type is not RuntimeEventType.SOURCE_RECORD_CHANGED:
        return (), ()

    targets = _event_targets(source_event)
    if not targets:
        return (), ()

    store = IntelligenceStore(session)
    triggered_watch_ids: list[str] = []
    trigger_event_ids: list[str] = []
    seen_watch_ids: set[str] = set()

    for target_type, target_id in targets:
        statement = select(IntelligenceWatchlistRecord).where(
            IntelligenceWatchlistRecord.target_type == target_type,
            IntelligenceWatchlistRecord.target_id == target_id,
            IntelligenceWatchlistRecord.status == WatchlistStatus.ACTIVE.value,
        )
        if workspace_id is not None:
            statement = statement.where(
                IntelligenceWatchlistRecord.workspace_id == workspace_id
            )

        for row in session.scalars(statement).all():
            if row.watchlist_item_id in seen_watch_ids:
                continue
            watch = WatchlistItem.model_validate_json(row.payload_json)
            _require_watch_row_identity(row, watch)
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
            seen_watch_ids.add(triggered.watchlist_item_id)
            triggered_watch_ids.append(triggered.watchlist_item_id)
            trigger_event_ids.append(attention.event_id)

    return tuple(triggered_watch_ids), tuple(trigger_event_ids)


def _event_targets(source_event: RuntimeEvent) -> tuple[tuple[str, str], ...]:
    """Map supported normalized source references to watch target identity."""

    targets: list[tuple[str, str]] = []
    for source_ref in source_event.source_record_refs:
        for kind in ("ceqa", "permit"):
            prefix = f"{kind}:"
            if source_ref.startswith(prefix):
                record_id = source_ref[len(prefix) :]
                if record_id:
                    targets.append((f"source_record:{kind}", record_id))
                break
    return tuple(dict.fromkeys(targets))


def _require_watch_row_identity(
    row: IntelligenceWatchlistRecord,
    watch: WatchlistItem,
) -> None:
    """Reject indexed/payload disagreement before mutating watch state."""

    target_type = (
        watch.target_type.value
        if hasattr(watch.target_type, "value")
        else str(watch.target_type)
    )
    expected = (
        watch.watchlist_item_id,
        watch.workspace_id,
        target_type,
        watch.target_id,
        watch.status.value,
        watch.priority,
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


def _attention_event(
    watch: WatchlistItem,
    source_event: RuntimeEvent,
    *,
    created_at: datetime,
) -> RuntimeEvent:
    """Build one deterministic retained attention event."""

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
