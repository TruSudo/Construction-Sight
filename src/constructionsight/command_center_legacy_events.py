"""Strict read-only original lead workflow transition-history verification.

Cross-check the current workflow projection against every persisted immutable
event row. This projects historical operator actions; it is not native
commercial authority or evidence of a live project.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_workflow_models import LeadWorkflowRecord
from constructionsight.storage.lead_workflow_orm import LeadWorkflowEventRecord

MAX_ORIGINAL_WORKFLOW_EVENTS = 500


def verified_original_workflow_events(
    session: Session, workflow: LeadWorkflowRecord,
) -> dict[str, Any]:
    """Fail closed when a stored event, status chain, or projection disagrees."""

    events = workflow.events
    if not events or len(events) > MAX_ORIGINAL_WORKFLOW_EVENTS:
        raise ValueError("original workflow has missing or excessive transition history")
    rows = session.scalars(
        select(LeadWorkflowEventRecord)
        .where(LeadWorkflowEventRecord.workflow_id == workflow.workflow_id)
        .order_by(LeadWorkflowEventRecord.id)
        .limit(MAX_ORIGINAL_WORKFLOW_EVENTS + 1)
    ).all()
    if len(rows) != len(events):
        raise ValueError("original workflow transition rows and projection disagree")

    transitions: list[dict[str, Any]] = []
    last_status = None
    last_at = None
    for index, (event, row) in enumerate(zip(events, rows, strict=True)):
        if index == 0:
            if event.previous_status is not None:
                raise ValueError("original workflow initial event has an unexpected predecessor")
        elif event.previous_status != last_status:
            raise ValueError("original workflow transition status chain is discontinuous")
        if last_at is not None and event.created_at < last_at:
            raise ValueError("original workflow transition timestamps are out of order")
        expected = event.model_dump(mode="json")
        actual = json.loads(row.payload_json)
        if (
            row.workflow_id != workflow.workflow_id
            or row.event_id != event.event_id
            or row.previous_status != (
                event.previous_status.value if event.previous_status else None
            )
            or row.current_status != event.current_status.value
            or row.reason != event.reason
            or row.observed_created_at != event.created_at.isoformat()
            or actual != expected
        ):
            raise ValueError("original workflow persisted event was changed or reordered")
        transitions.append({
            "sequence": index,
            "event_id": event.event_id,
            "previous_status": row.previous_status,
            "current_status": row.current_status,
            "reason": row.reason,
            "recorded_at": row.observed_created_at,
            "historical_only": True,
            "commercial_authority_granted": False,
        })
        last_status = event.current_status
        last_at = event.created_at
    if last_status != workflow.status:
        raise ValueError("original workflow final status differs from event history")
    return {
        "history_integrity_validated": True,
        "event_count": len(transitions),
        "current_status": workflow.status.value,
        "transitions": transitions,
        "original_operator_actions_only": True,
        "outreach_authorized": False,
        "bid_authorized": False,
    }
