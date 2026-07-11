"""Authoritative current-state service for immutable result-ledger records."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.result_ledger_models import (
    ResultLedgerAuthorityApplyReport,
    ResultLedgerAuthorityEvent,
    ResultLedgerAuthorityRecord,
    ResultLedgerRecord,
    ResultLedgerStatus,
)
from constructionsight.result_ledger_service import (
    compute_result_ledger_id,
    compute_result_share_id,
)
from constructionsight.storage.lead_workflow_orm import ResultLedgerRecordRow
from constructionsight.storage.lead_workflow_store import store_result_ledger_record
from constructionsight.storage.result_ledger_authority_orm import (
    ResultLedgerAuthorityRecordRow,
)
from constructionsight.storage.result_ledger_authority_store import (
    compare_and_swap_result_ledger_authority_record,
    create_result_ledger_authority_record,
    store_result_ledger_authority_event,
)


class ResultLedgerAuthorityError(ValueError):
    """Raised when an authoritative result cannot be safely established."""


def load_result_ledger_authority(
    session: Session,
    workflow_id: str,
) -> ResultLedgerAuthorityRecord | None:
    """Load and integrity-check the current authority pointer for a workflow."""

    row = session.execute(
        select(ResultLedgerAuthorityRecordRow).where(
            ResultLedgerAuthorityRecordRow.workflow_id == workflow_id
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    payload = _payload_object(
        row.payload_json,
        record_label="result ledger authority",
        record_id=row.authority_id,
    )
    authority = ResultLedgerAuthorityRecord.model_validate(payload)
    indexed_values: dict[str, object] = {
        "authority_id": row.authority_id,
        "workflow_id": row.workflow_id,
        "current_ledger_id": row.current_ledger_id,
        "revision": row.revision,
        "updated_at": row.observed_updated_at,
    }
    payload_values: dict[str, object] = {
        "authority_id": authority.authority_id,
        "workflow_id": authority.workflow_id,
        "current_ledger_id": authority.current_ledger_id,
        "revision": authority.revision,
        "updated_at": authority.updated_at.isoformat(),
    }
    drifted = [
        field_name
        for field_name, indexed_value in indexed_values.items()
        if payload_values[field_name] != indexed_value
    ]
    if drifted:
        fields = ", ".join(sorted(drifted))
        raise ResultLedgerAuthorityError(
            "result ledger authority indexed fields disagree with payload for "
            f"{workflow_id}: {fields}"
        )
    ledger = load_result_ledger_record(session, authority.current_ledger_id)
    if ledger.workflow_id != workflow_id:
        raise ResultLedgerAuthorityError(
            "authoritative result ledger belongs to a different workflow: "
            f"{authority.current_ledger_id}"
        )
    return authority


def load_result_ledger_record(
    session: Session,
    ledger_id: str,
) -> ResultLedgerRecord:
    """Load and integrity-check one immutable result-ledger row."""

    row = session.execute(
        select(ResultLedgerRecordRow).where(ResultLedgerRecordRow.ledger_id == ledger_id)
    ).scalar_one_or_none()
    if row is None:
        raise ResultLedgerAuthorityError(f"result ledger not found: {ledger_id}")
    payload = _payload_object(
        row.payload_json,
        record_label="result ledger",
        record_id=ledger_id,
    )
    ledger = ResultLedgerRecord.model_validate(payload)
    share_record_id = ledger.share.share_record_id if ledger.share is not None else None
    decided_date = ledger.decided_date.isoformat() if ledger.decided_date else None
    indexed_values: dict[str, object] = {
        "ledger_id": row.ledger_id,
        "workflow_id": row.workflow_id,
        "package_id": row.package_id,
        "status": row.status,
        "decided_date": row.decided_date,
        "gross_value": row.gross_value,
        "share_status": row.share_status,
        "share_record_id": row.share_record_id,
        "created_at": row.observed_created_at,
    }
    payload_values: dict[str, object] = {
        "ledger_id": ledger.ledger_id,
        "workflow_id": ledger.workflow_id,
        "package_id": ledger.package_id,
        "status": ledger.status.value,
        "decided_date": decided_date,
        "gross_value": ledger.gross_value,
        "share_status": ledger.share_status.value,
        "share_record_id": share_record_id,
        "created_at": ledger.created_at.isoformat(),
    }
    drifted = [
        field_name
        for field_name, indexed_value in indexed_values.items()
        if payload_values[field_name] != indexed_value
    ]
    if drifted:
        fields = ", ".join(sorted(drifted))
        raise ResultLedgerAuthorityError(
            f"result ledger indexed fields disagree with payload for {ledger_id}: {fields}"
        )
    _require_canonical_result_identity(ledger)
    return ledger


def apply_authoritative_result_ledger(
    session: Session,
    *,
    workflow: LeadWorkflowRecord,
    ledger: ResultLedgerRecord,
    expected_current_ledger_id: str | None,
    reason: str,
) -> ResultLedgerAuthorityApplyReport:
    """Establish or correct one authoritative result with append-only history."""

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise ResultLedgerAuthorityError("result authority reason must not be blank")
    _require_ledger_matches_workflow(workflow, ledger)
    _require_canonical_result_identity(ledger)
    _require_workflow_result_compatibility(workflow.status, ledger.status)

    current = load_result_ledger_authority(session, workflow.workflow_id)
    if current is None:
        if expected_current_ledger_id is not None:
            raise ResultLedgerAuthorityError(
                "result authority does not yet exist; expected current ledger must be omitted"
            )
        previous_ledger_id = None
        revision = 1
    else:
        if expected_current_ledger_id is None:
            raise ResultLedgerAuthorityError(
                "expected current ledger is required when correcting result authority"
            )
        if current.current_ledger_id != expected_current_ledger_id:
            raise ResultLedgerAuthorityError(
                "result authority current ledger does not match operator expectation: "
                f"expected {expected_current_ledger_id}, "
                f"observed {current.current_ledger_id}"
            )
        if current.current_ledger_id == ledger.ledger_id:
            raise ResultLedgerAuthorityError(
                "result authority correction must select a different ledger record"
            )
        previous_ledger_id = current.current_ledger_id
        revision = current.revision + 1

    authority = ResultLedgerAuthorityRecord(
        authority_id=_authority_id(workflow.workflow_id),
        workflow_id=workflow.workflow_id,
        current_ledger_id=ledger.ledger_id,
        revision=revision,
    )
    event = ResultLedgerAuthorityEvent(
        event_id=_authority_event_id(
            workflow_id=workflow.workflow_id,
            previous_ledger_id=previous_ledger_id,
            current_ledger_id=ledger.ledger_id,
            revision=revision,
            reason=normalized_reason,
        ),
        workflow_id=workflow.workflow_id,
        previous_ledger_id=previous_ledger_id,
        current_ledger_id=ledger.ledger_id,
        revision=revision,
        reason=normalized_reason,
    )

    try:
        with session.begin_nested():
            store_result_ledger_record(session, ledger)
            if current is None:
                create_result_ledger_authority_record(session, authority)
            else:
                compare_and_swap_result_ledger_authority_record(
                    session,
                    authority,
                    expected_current_ledger_id=current.current_ledger_id,
                    expected_revision=current.revision,
                )
            store_result_ledger_authority_event(session, event)
            session.flush()
    except ValueError as exc:
        raise ResultLedgerAuthorityError(str(exc)) from exc

    return ResultLedgerAuthorityApplyReport(
        authority=authority,
        event=event,
        ledger=ledger,
    )


def _require_ledger_matches_workflow(
    workflow: LeadWorkflowRecord,
    ledger: ResultLedgerRecord,
) -> None:
    if ledger.workflow_id != workflow.workflow_id:
        raise ResultLedgerAuthorityError(
            "result ledger workflow does not match reviewed workflow"
        )
    if ledger.package_id != workflow.package_id:
        raise ResultLedgerAuthorityError(
            "result ledger package does not match reviewed workflow package"
        )


def _require_canonical_result_identity(ledger: ResultLedgerRecord) -> None:
    expected_ledger_id = compute_result_ledger_id(ledger)
    if ledger.ledger_id != expected_ledger_id:
        raise ResultLedgerAuthorityError(
            "result ledger id does not match canonical content identity: "
            f"{ledger.ledger_id}"
        )
    if ledger.reasons != sorted(ledger.reasons):
        raise ResultLedgerAuthorityError(
            "result ledger reasons must use canonical sorted order"
        )
    if ledger.share is not None:
        expected_share_id = compute_result_share_id(ledger.share)
        if ledger.share.share_record_id != expected_share_id:
            raise ResultLedgerAuthorityError(
                "result share id does not match canonical content identity: "
                f"{ledger.share.share_record_id}"
            )


def _require_workflow_result_compatibility(
    workflow_status: LeadWorkflowStatus,
    result_status: ResultLedgerStatus,
) -> None:
    if workflow_status == LeadWorkflowStatus.CLOSED_SUCCESS:
        if result_status != ResultLedgerStatus.WON:
            raise ResultLedgerAuthorityError(
                "closed_success workflow requires a won authoritative result"
            )
        return
    if workflow_status == LeadWorkflowStatus.CLOSED_NO_FIT:
        if result_status not in {ResultLedgerStatus.LOST, ResultLedgerStatus.NO_FIT}:
            raise ResultLedgerAuthorityError(
                "closed_no_fit workflow requires a lost or no_fit authoritative result"
            )
        return
    if result_status not in {ResultLedgerStatus.OPEN, ResultLedgerStatus.UNKNOWN}:
        raise ResultLedgerAuthorityError(
            "non-final workflow may have only open or unknown authoritative result"
        )


def _authority_id(workflow_id: str) -> str:
    return f"result-ledger-authority:{_short_hash(workflow_id)}"


def _authority_event_id(
    *,
    workflow_id: str,
    previous_ledger_id: str | None,
    current_ledger_id: str,
    revision: int,
    reason: str,
) -> str:
    basis = "|".join(
        [
            workflow_id,
            previous_ledger_id or "",
            current_ledger_id,
            str(revision),
            reason,
        ]
    )
    return f"result-ledger-authority-event:{_short_hash(basis)}"


def _payload_object(
    payload_json: str,
    *,
    record_label: str,
    record_id: str,
) -> dict[str, Any]:
    try:
        data: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise ResultLedgerAuthorityError(
            f"malformed {record_label} payload JSON for record: {record_id}"
        ) from exc
    if not isinstance(data, dict):
        raise ResultLedgerAuthorityError(
            f"{record_label} payload must be a JSON object for record: {record_id}"
        )
    return {str(key): value for key, value in data.items()}


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
