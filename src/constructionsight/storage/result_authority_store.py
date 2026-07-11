"""Store helpers for result-ledger authority heads and audit events."""

from __future__ import annotations

import json

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.result_authority_models import (
    ResultAuthorityEvent,
    ResultAuthorityHead,
)
from constructionsight.storage.result_authority_orm import (
    ResultAuthorityEventRow,
    ResultAuthorityHeadRow,
)


def create_result_authority_head(
    session: Session,
    head: ResultAuthorityHead,
) -> ResultAuthorityHeadRow:
    """Create the first serialized authority head for a workflow."""

    row = ResultAuthorityHeadRow(
        workflow_id=head.workflow_id,
        current_ledger_id=head.current_ledger_id,
        current_revision=head.current_revision,
        observed_updated_at=head.updated_at.isoformat(),
        payload_json=_payload_json(head.to_dict()),
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        raise ValueError(
            f"result authority head already exists for workflow: {head.workflow_id}"
        ) from exc
    return row


def compare_and_swap_result_authority_head(
    session: Session,
    head: ResultAuthorityHead,
    *,
    expected_current_ledger_id: str,
    expected_revision: int,
) -> ResultAuthorityHeadRow:
    """Atomically move a head only when the reviewed tip is still current."""

    updated_id = session.execute(
        update(ResultAuthorityHeadRow)
        .where(
            ResultAuthorityHeadRow.workflow_id == head.workflow_id,
            ResultAuthorityHeadRow.current_ledger_id == expected_current_ledger_id,
            ResultAuthorityHeadRow.current_revision == expected_revision,
        )
        .values(
            current_ledger_id=head.current_ledger_id,
            current_revision=head.current_revision,
            observed_updated_at=head.updated_at.isoformat(),
            payload_json=_payload_json(head.to_dict()),
        )
        .returning(ResultAuthorityHeadRow.id)
    ).scalar_one_or_none()
    if updated_id is None:
        raise ValueError(
            "result authority changed after operator review for workflow: "
            f"{head.workflow_id}"
        )
    return session.execute(
        select(ResultAuthorityHeadRow).where(ResultAuthorityHeadRow.id == updated_id)
    ).scalar_one()


def store_result_authority_event(
    session: Session,
    event: ResultAuthorityEvent,
) -> ResultAuthorityEventRow:
    """Append one immutable authority event, allowing semantic idempotent replay."""

    payload_json = _payload_json(event.to_dict())
    existing = session.execute(
        select(ResultAuthorityEventRow).where(
            ResultAuthorityEventRow.event_id == event.event_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if _semantic_event_payload(existing.payload_json) != _semantic_event_payload(
            payload_json
        ):
            raise ValueError(
                f"result authority event identity collision: {event.event_id}"
            )
        return existing
    row = ResultAuthorityEventRow(
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
            "result authority event already exists for workflow revision: "
            f"{event.workflow_id} revision {event.revision}"
        ) from exc
    return row


def _semantic_event_payload(payload_json: str) -> str:
    """Return event content excluding its observation timestamp."""

    data = json.loads(payload_json)
    if not isinstance(data, dict):
        raise ValueError("result authority event payload must be a JSON object")
    data.pop("created_at", None)
    return _payload_json({str(key): value for key, value in data.items()})


def _payload_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON payload."""

    return json.dumps(payload, sort_keys=True)
