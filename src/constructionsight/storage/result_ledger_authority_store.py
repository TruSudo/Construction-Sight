"""Store helpers for authoritative result-ledger state and history."""

from __future__ import annotations

import json

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.result_ledger_models import (
    ResultLedgerAuthorityEvent,
    ResultLedgerAuthorityRecord,
)
from constructionsight.storage.result_ledger_authority_orm import (
    ResultLedgerAuthorityEventRow,
    ResultLedgerAuthorityRecordRow,
)


def create_result_ledger_authority_record(
    session: Session,
    authority: ResultLedgerAuthorityRecord,
) -> ResultLedgerAuthorityRecordRow:
    """Create the first current authority pointer for a workflow."""

    payload_json = _payload_json(authority.to_dict())
    row = ResultLedgerAuthorityRecordRow(
        authority_id=authority.authority_id,
        workflow_id=authority.workflow_id,
        current_ledger_id=authority.current_ledger_id,
        revision=authority.revision,
        observed_updated_at=authority.updated_at.isoformat(),
        payload_json=payload_json,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(
            "result ledger authority already exists for workflow: "
            f"{authority.workflow_id}"
        ) from exc
    return row


def compare_and_swap_result_ledger_authority_record(
    session: Session,
    authority: ResultLedgerAuthorityRecord,
    *,
    expected_current_ledger_id: str,
    expected_revision: int,
) -> ResultLedgerAuthorityRecordRow:
    """Atomically replace a current pointer only when reviewed state is unchanged."""

    payload_json = _payload_json(authority.to_dict())
    result = session.execute(
        update(ResultLedgerAuthorityRecordRow)
        .where(
            ResultLedgerAuthorityRecordRow.workflow_id == authority.workflow_id,
            ResultLedgerAuthorityRecordRow.authority_id == authority.authority_id,
            ResultLedgerAuthorityRecordRow.current_ledger_id
            == expected_current_ledger_id,
            ResultLedgerAuthorityRecordRow.revision == expected_revision,
        )
        .values(
            current_ledger_id=authority.current_ledger_id,
            revision=authority.revision,
            observed_updated_at=authority.updated_at.isoformat(),
            payload_json=payload_json,
        )
    )
    if result.rowcount != 1:
        raise ValueError(
            "result ledger authority changed after operator review for workflow: "
            f"{authority.workflow_id}"
        )
    return session.execute(
        select(ResultLedgerAuthorityRecordRow).where(
            ResultLedgerAuthorityRecordRow.workflow_id == authority.workflow_id
        )
    ).scalar_one()


def store_result_ledger_authority_event(
    session: Session,
    event: ResultLedgerAuthorityEvent,
) -> ResultLedgerAuthorityEventRow:
    """Insert one immutable authority event, allowing semantic idempotent replay."""

    payload_json = _payload_json(event.to_dict())
    existing = session.execute(
        select(ResultLedgerAuthorityEventRow).where(
            ResultLedgerAuthorityEventRow.event_id == event.event_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if _authority_event_semantic_payload(existing.payload_json) != (
            _authority_event_semantic_payload(payload_json)
        ):
            raise ValueError(
                f"result ledger authority event identity collision: {event.event_id}"
            )
        return existing
    row = ResultLedgerAuthorityEventRow(
        event_id=event.event_id,
        workflow_id=event.workflow_id,
        previous_ledger_id=event.previous_ledger_id,
        current_ledger_id=event.current_ledger_id,
        revision=event.revision,
        reason=event.reason,
        observed_created_at=event.created_at.isoformat(),
        payload_json=payload_json,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(
            "result ledger authority revision already exists for workflow: "
            f"{event.workflow_id} revision {event.revision}"
        ) from exc
    return row


def _authority_event_semantic_payload(payload_json: str) -> str:
    """Return authority-event content excluding observation timestamp."""

    data = json.loads(payload_json)
    if not isinstance(data, dict):
        raise ValueError("result ledger authority event payload must be a JSON object")
    data.pop("created_at", None)
    return _payload_json({str(key): value for key, value in data.items()})


def _payload_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON payload."""

    return json.dumps(payload, sort_keys=True)
