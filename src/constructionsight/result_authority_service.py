"""Governed read and write service for authoritative result-ledger history."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_operator_service import load_persisted_lead_workflow
from constructionsight.money import DecimalInput, money_decimal, rate_decimal, storage_money_text
from constructionsight.result_authority_models import (
    ResultAuthorityApplyReport,
    ResultAuthorityEvent,
    ResultAuthorityHead,
    ResultAuthoritySnapshot,
)
from constructionsight.result_ledger_models import ResultLedgerRecord, ResultLedgerStatus
from constructionsight.result_ledger_service import (
    build_result_ledger_record,
    supersede_result_ledger_record,
    validate_result_ledger_history,
)
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_result_ledger_record
from constructionsight.storage.result_authority_orm import (
    ResultAuthorityEventRow,
    ResultAuthorityHeadRow,
)
from constructionsight.storage.result_authority_store import (
    compare_and_swap_result_authority_head,
    create_result_authority_head,
    store_result_authority_event,
)


class ResultAuthorityError(ValueError):
    """Raised when result authority is absent, stale, malformed, or contradictory."""


def load_result_authority_snapshot(
    session: Session,
    workflow_id: str,
) -> ResultAuthoritySnapshot | None:
    """Load and integrity-check one complete result history and authority head."""

    history = load_result_ledger_history(session, workflow_id)
    head = _load_result_authority_head(session, workflow_id)
    if not history:
        if head is not None:
            raise ResultAuthorityError(
                f"result authority head exists without ledger history: {workflow_id}"
            )
        return None
    current = validate_result_ledger_history(history)
    if head is not None:
        if head.current_ledger_id != current.ledger_id:
            raise ResultAuthorityError(
                "result authority head does not match validated ledger tip for workflow: "
                f"{workflow_id}"
            )
        if head.current_revision != current.revision:
            raise ResultAuthorityError(
                "result authority head revision does not match ledger tip for workflow: "
                f"{workflow_id}"
            )
    return ResultAuthoritySnapshot(
        workflow_id=workflow_id,
        current=current,
        history=history,
        head=head,
    )


def load_result_ledger_history(
    session: Session,
    workflow_id: str,
) -> list[ResultLedgerRecord]:
    """Load all immutable result revisions and reject indexed/payload drift."""

    rows = session.execute(
        select(ResultLedgerRecordRow)
        .where(ResultLedgerRecordRow.workflow_id == workflow_id)
        .order_by(ResultLedgerRecordRow.id)
    ).scalars()
    records = [_ledger_from_row(row) for row in rows]
    if records:
        validate_result_ledger_history(records)
    return records


def list_result_authority_events(
    session: Session,
    workflow_id: str,
) -> list[ResultAuthorityEvent]:
    """Load events and bind each claim to the immutable ledger history."""

    rows = session.execute(
        select(ResultAuthorityEventRow)
        .where(ResultAuthorityEventRow.workflow_id == workflow_id)
        .order_by(ResultAuthorityEventRow.revision)
    ).scalars()
    events = [_event_from_row(row) for row in rows]
    revisions = [event.revision for event in events]
    if revisions != sorted(set(revisions)):
        raise ResultAuthorityError(
            f"result authority events contain duplicate or unordered revisions: {workflow_id}"
        )
    history_by_revision = {
        ledger.revision: ledger
        for ledger in load_result_ledger_history(session, workflow_id)
    }
    for event in events:
        ledger = history_by_revision.get(event.revision)
        if ledger is None:
            raise ResultAuthorityError(
                "result authority event references a missing ledger revision: "
                f"{workflow_id} revision {event.revision}"
            )
        if event.current_ledger_id != ledger.ledger_id:
            raise ResultAuthorityError(
                "result authority event current ledger disagrees with history: "
                f"{event.event_id}"
            )
        if event.current_content_digest != ledger.content_digest:
            raise ResultAuthorityError(
                "result authority event current content digest disagrees with history: "
                f"{event.event_id}"
            )
        if event.previous_ledger_id != ledger.supersedes_ledger_id:
            raise ResultAuthorityError(
                "result authority event predecessor disagrees with history: "
                f"{event.event_id}"
            )
        predecessor = history_by_revision.get(event.revision - 1)
        expected_previous_digest = (
            predecessor.content_digest if predecessor is not None else None
        )
        if event.previous_content_digest != expected_previous_digest:
            raise ResultAuthorityError(
                "result authority event predecessor content digest disagrees with history: "
                f"{event.event_id}"
            )
        if event.revision > 1 and event.reason != ledger.correction_reason:
            raise ResultAuthorityError(
                "result authority event correction reason disagrees with history: "
                f"{event.event_id}"
            )
    return events


def apply_authoritative_result(
    session: Session,
    *,
    workflow_id: str,
    expected_current_ledger_id: str | None,
    status: ResultLedgerStatus,
    authority_reason: str,
    decided_date: date | None = None,
    gross_value: DecimalInput | None = None,
    share_rate: DecimalInput | None = None,
    outcome_reasons: list[str] | None = None,
) -> ResultAuthorityApplyReport:
    """Create or correct one result with explicit stale-state and audit controls."""

    normalized_reason = authority_reason.strip()
    if not normalized_reason:
        raise ResultAuthorityError("result authority reason must not be blank")
    workflow = load_persisted_lead_workflow(session, workflow_id)
    snapshot = load_result_authority_snapshot(session, workflow_id)

    if snapshot is None:
        if expected_current_ledger_id is not None:
            raise ResultAuthorityError(
                "result authority current ledger does not match the operator expectation: "
                f"expected {expected_current_ledger_id}, observed none"
            )
        ledger = build_result_ledger_record(
            workflow=workflow,
            status=status,
            decided_date=decided_date,
            gross_value=gross_value,
            share_rate=share_rate,
            reasons=outcome_reasons,
        )
        previous_ledger_id = None
        previous_content_digest = None
        prior_revision = 0
    else:
        current = snapshot.current
        if expected_current_ledger_id != current.ledger_id:
            expected = expected_current_ledger_id or "none"
            raise ResultAuthorityError(
                "result authority current ledger does not match the operator expectation: "
                f"expected {expected}, observed {current.ledger_id}"
            )
        if _same_outcome(
            current,
            status=status,
            decided_date=decided_date,
            gross_value=gross_value,
            share_rate=share_rate,
            outcome_reasons=outcome_reasons,
        ):
            raise ResultAuthorityError(
                "result authority correction must change the authoritative outcome payload"
            )
        ledger = supersede_result_ledger_record(
            current=current,
            status=status,
            correction_reason=normalized_reason,
            decided_date=decided_date,
            gross_value=gross_value,
            share_rate=share_rate,
            reasons=outcome_reasons,
        )
        previous_ledger_id = current.ledger_id
        previous_content_digest = current.content_digest
        prior_revision = current.revision

    head = ResultAuthorityHead(
        workflow_id=workflow_id,
        current_ledger_id=ledger.ledger_id,
        current_revision=ledger.revision,
    )
    event = ResultAuthorityEvent(
        event_id=_event_id(
            workflow_id=workflow_id,
            previous_ledger_id=previous_ledger_id,
            previous_content_digest=previous_content_digest,
            current_ledger_id=ledger.ledger_id,
            current_content_digest=ledger.content_digest or "",
            revision=ledger.revision,
            reason=normalized_reason,
        ),
        workflow_id=workflow_id,
        previous_ledger_id=previous_ledger_id,
        previous_content_digest=previous_content_digest,
        current_ledger_id=ledger.ledger_id,
        current_content_digest=ledger.content_digest or "",
        revision=ledger.revision,
        reason=normalized_reason,
    )

    try:
        with session.begin_nested():
            if snapshot is None:
                store_result_ledger_record(session, ledger)
                create_result_authority_head(session, head)
            else:
                if snapshot.head is None:
                    bootstrap_head = ResultAuthorityHead(
                        workflow_id=workflow_id,
                        current_ledger_id=previous_ledger_id or "",
                        current_revision=prior_revision,
                    )
                    create_result_authority_head(session, bootstrap_head)
                store_result_ledger_record(session, ledger)
                compare_and_swap_result_authority_head(
                    session,
                    head,
                    expected_current_ledger_id=previous_ledger_id or "",
                    expected_revision=prior_revision,
                )
            store_result_authority_event(session, event)
            session.flush()
    except ValueError as exc:
        raise ResultAuthorityError(str(exc)) from exc

    return ResultAuthorityApplyReport(
        previous_ledger_id=previous_ledger_id,
        current=ledger,
        head=head,
        event=event,
    )


def _load_result_authority_head(
    session: Session,
    workflow_id: str,
) -> ResultAuthorityHead | None:
    row = session.execute(
        select(ResultAuthorityHeadRow).where(
            ResultAuthorityHeadRow.workflow_id == workflow_id
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    payload = _decode_json_object(
        row.payload_json,
        record_label="result authority head",
        record_id=workflow_id,
    )
    try:
        head = ResultAuthorityHead.model_validate(payload)
    except ValueError as exc:
        raise ResultAuthorityError(
            f"invalid result authority head payload for workflow: {workflow_id}"
        ) from exc
    indexed = (
        row.workflow_id,
        row.current_ledger_id,
        row.current_revision,
        row.observed_updated_at,
    )
    payload_values = (
        head.workflow_id,
        head.current_ledger_id,
        head.current_revision,
        head.updated_at.isoformat(),
    )
    if indexed != payload_values:
        raise ResultAuthorityError(
            f"result authority head indexed fields disagree with payload: {workflow_id}"
        )
    return head


def _ledger_from_row(row: ResultLedgerRecordRow) -> ResultLedgerRecord:
    payload = _decode_json_object(
        row.payload_json,
        record_label="result ledger",
        record_id=row.ledger_id,
    )
    try:
        ledger = ResultLedgerRecord.model_validate(payload)
    except ValueError as exc:
        raise ResultAuthorityError(
            f"invalid result ledger payload for record: {row.ledger_id}"
        ) from exc
    share_record_id = ledger.share.share_record_id if ledger.share is not None else None
    decided_date = ledger.decided_date.isoformat() if ledger.decided_date else None
    indexed = (
        row.ledger_id,
        row.workflow_id,
        row.package_id,
        row.status,
        row.decided_date,
        row.gross_value,
        row.gross_value_exact,
        row.share_status,
        row.share_record_id,
        row.observed_created_at,
    )
    payload_values = (
        ledger.ledger_id,
        ledger.workflow_id,
        ledger.package_id,
        ledger.status.value,
        decided_date,
        None if ledger.gross_value is None else float(ledger.gross_value),
        None if ledger.gross_value is None else storage_money_text(ledger.gross_value),
        ledger.share_status.value,
        share_record_id,
        ledger.created_at.isoformat(),
    )
    if indexed != payload_values:
        raise ResultAuthorityError(
            f"result ledger indexed fields disagree with payload: {row.ledger_id}"
        )
    return ledger


def _event_from_row(row: ResultAuthorityEventRow) -> ResultAuthorityEvent:
    payload = _decode_json_object(
        row.payload_json,
        record_label="result authority event",
        record_id=row.event_id,
    )
    try:
        event = ResultAuthorityEvent.model_validate(payload)
    except ValueError as exc:
        raise ResultAuthorityError(
            f"invalid result authority event payload for record: {row.event_id}"
        ) from exc
    indexed = (
        row.event_id,
        row.workflow_id,
        row.previous_ledger_id,
        row.current_ledger_id,
        row.revision,
        row.reason,
        row.observed_created_at,
    )
    payload_values = (
        event.event_id,
        event.workflow_id,
        event.previous_ledger_id,
        event.current_ledger_id,
        event.revision,
        event.reason,
        event.created_at.isoformat(),
    )
    if indexed != payload_values:
        raise ResultAuthorityError(
            f"result authority event indexed fields disagree with payload: {row.event_id}"
        )
    return event


def _decode_json_object(
    payload_json: str,
    *,
    record_label: str,
    record_id: str,
) -> dict[str, Any]:
    try:
        value: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ResultAuthorityError(
            f"malformed {record_label} payload JSON for record: {record_id}"
        ) from exc
    if not isinstance(value, dict):
        raise ResultAuthorityError(
            f"{record_label} payload must be a JSON object for record: {record_id}"
        )
    return {str(key): item for key, item in value.items()}


def _same_outcome(
    current: ResultLedgerRecord,
    *,
    status: ResultLedgerStatus,
    decided_date: date | None,
    gross_value: DecimalInput | None,
    share_rate: DecimalInput | None,
    outcome_reasons: list[str] | None,
) -> bool:
    current_rate = current.share.share_rate if current.share is not None else None
    try:
        normalized_gross = (
            money_decimal(gross_value, field_name="gross_value")
            if gross_value is not None
            else None
        )
        normalized_rate = (
            rate_decimal(share_rate, field_name="share_rate")
            if share_rate is not None
            else None
        )
    except ValueError:
        return False
    return (
        current.status == status
        and current.decided_date == decided_date
        and current.gross_value == normalized_gross
        and current_rate == normalized_rate
        and current.reasons == (outcome_reasons or [])
    )


def _event_id(
    *,
    workflow_id: str,
    previous_ledger_id: str | None,
    previous_content_digest: str | None,
    current_ledger_id: str,
    current_content_digest: str,
    revision: int,
    reason: str,
) -> str:
    basis = "|".join(
        [
            workflow_id,
            previous_ledger_id or "none",
            previous_content_digest or "none",
            current_ledger_id,
            current_content_digest,
            str(revision),
            reason,
        ]
    )
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"result-authority-event:{digest}"
