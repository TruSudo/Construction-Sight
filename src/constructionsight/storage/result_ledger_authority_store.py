"""Store helpers for authoritative result-ledger state and history."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.result_ledger_models import (
    ResultLedgerAuthorityEvent,
    ResultLedgerAuthorityRecord,
)
from constructionsight.storage.result_ledger_authority_orm import (
    ResultLedgerAuthorityEventRow,
    ResultLedgerAuthorityRecordRow,
)


def store_result_ledger_authority_record(
    session: Session,
    authority: ResultLedgerAuthorityRecord,
) -> ResultLedgerAuthorityRecordRow:
    """Insert or update the one current authority pointer for a workflow."""

    session.flush()
    payload_json = _payload_json(authority.to_dict())
    existing = session.execute(
        select(ResultLedgerAuthorityRecordRow).where(
            ResultLedgerAuthorityRecordRow.workflow_id == authority.workflow_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = ResultLedgerAuthorityRecordRow(
            authority_id=authority.authority_id,
            workflow_id=authority.workflow_id,
            current_ledger_id=authority.current_ledger_id,
            revision=authority.revision,
            observed_updated_at=authority.updated_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    if existing.authority_id != authority.authority_id:
        raise ValueError(
            "result ledger authority identity changed for workflow: "
            f"{authority.workflow_id}"
        )
    if authority.revision <= existing.revision:
        raise ValueError(
            "result ledger authority revision must increase for workflow: "
            f"{authority.workflow_id}"
        )
    existing.current_ledger_id = authority.current_ledger_id
    existing.revision = authority.revision
    existing.observed_updated_at = authority.updated_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_result_ledger_authority_event(
    session: Session,
    event: ResultLedgerAuthorityEvent,
) -> ResultLedgerAuthorityEventRow:
    """Insert one immutable authority event, allowing exact idempotent replay."""

    session.flush()
    payload_json = _payload_json(event.to_dict())
    existing = session.execute(
        select(ResultLedgerAuthorityEventRow).where(
            ResultLedgerAuthorityEventRow.event_id == event.event_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.payload_json != payload_json:
            raise ValueError(
                f"result ledger authority event identity collision: {event.event_id}"
            )
        return existing
    existing = ResultLedgerAuthorityEventRow(
        event_id=event.event_id,
        workflow_id=event.workflow_id,
        previous_ledger_id=event.previous_ledger_id,
        current_ledger_id=event.current_ledger_id,
        revision=event.revision,
        reason=event.reason,
        observed_created_at=event.created_at.isoformat(),
        payload_json=payload_json,
    )
    session.add(existing)
    return existing


def _payload_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON payload."""

    return json.dumps(payload, sort_keys=True)
