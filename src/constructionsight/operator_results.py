"""Read-only, revision-aware result and share inspection for the local operator.

A calculated result share is not evidence of royalty entitlement or payment.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.result_ledger_models import ResultLedgerRecord
from constructionsight.result_ledger_service import (
    calculate_share_minor_units,
    money_minor_units,
    share_rate_ppm_units,
    validate_result_ledger_history,
)
from constructionsight.storage.lead_workflow_orm import (
    LeadWorkflowRecordRow,
    ResultLedgerRecordRow,
    ResultShareRecordRow,
)

MAX_REVISIONS_PER_WORKFLOW = 100


def read_validated_result_history(
    session: Session, workflow_id: str,
) -> dict[str, Any] | None:
    """Read exact original result revisions and share receipts, or no ledger.

    The same integrity validation is used for the existing original operator
    results view and the native source-scoped historical lineage.
    """

    rows = session.scalars(
        select(ResultLedgerRecordRow)
        .where(ResultLedgerRecordRow.workflow_id == workflow_id)
        .order_by(ResultLedgerRecordRow.id)
        .limit(MAX_REVISIONS_PER_WORKFLOW + 1)
    ).all()
    if not rows:
        return None
    if len(rows) > MAX_REVISIONS_PER_WORKFLOW:
        raise ValueError("result history exceeds the inspection limit")
    history: list[ResultLedgerRecord] = []
    for row in rows:
        record = ResultLedgerRecord.model_validate(json.loads(row.payload_json))
        expected = (
            record.ledger_id,
            record.workflow_id,
            record.package_id,
            record.status.value,
            record.decided_date.isoformat() if record.decided_date else None,
            record.gross_value,
            record.share_status.value,
            record.share.share_record_id if record.share else None,
            record.created_at.isoformat(),
        )
        actual = (
            row.ledger_id,
            row.workflow_id,
            row.package_id,
            row.status,
            row.decided_date,
            row.gross_value,
            row.share_status,
            row.share_record_id,
            row.observed_created_at,
        )
        if actual != expected or record.workflow_id != workflow_id:
            raise ValueError("result ledger index and retained revision disagree")
        expected_minor = (
            money_minor_units(record.gross_value, field_name="gross_value")
            if record.gross_value is not None else None
        )
        if row.gross_value_minor != expected_minor:
            raise ValueError("result ledger indexed exact money differs from payload")
        history.append(record)
    current = validate_result_ledger_history(history)
    workflow = session.scalar(
        select(LeadWorkflowRecordRow)
        .where(LeadWorkflowRecordRow.workflow_id == workflow_id)
    )
    if workflow is None or workflow.package_id != current.package_id:
        raise ValueError("result ledger references missing or inconsistent workflow")
    # Verify every retained share, including superseded revisions. A current
    # no-share outcome cannot conceal an altered previous calculated share.
    for revision in history:
        if revision.share is None:
            continue
        share = revision.share
        stored_share = session.scalar(
            select(ResultShareRecordRow)
            .where(ResultShareRecordRow.share_record_id == share.share_record_id)
        )
        gross_minor = money_minor_units(share.gross_value, field_name="gross_value")
        rate_ppm = share_rate_ppm_units(share.share_rate)
        share_minor = calculate_share_minor_units(gross_minor, rate_ppm)
        if (
            stored_share is None
            or stored_share.workflow_id != workflow_id
            or stored_share.gross_value != share.gross_value
            or stored_share.gross_value_minor != gross_minor
            or stored_share.share_rate != share.share_rate
            or stored_share.share_rate_ppm != rate_ppm
            or stored_share.share_value != share.share_value
            or stored_share.share_value_minor != share_minor
            or json.loads(stored_share.payload_json) != share.model_dump(mode="json")
        ):
            raise ValueError("retained calculated share and exact money index disagree")
    return {
        "workflow_id": workflow_id,
        "package_id": current.package_id,
        "current": current.to_dict(),
        "revision_count": len(history),
        "history": [record.to_dict() for record in history],
    }


def build_result_ledger_snapshot(
    session: Session, *, limit: int = 25, offset: int = 0
) -> dict[str, Any]:
    """Read bounded, complete, validated histories for exact persisted workflow keys."""

    if not 1 <= limit <= 50 or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid result ledger page bounds")
    total = session.scalar(
        select(func.count(func.distinct(ResultLedgerRecordRow.workflow_id)))
    ) or 0
    workflow_ids = session.scalars(
        select(ResultLedgerRecordRow.workflow_id)
        .group_by(ResultLedgerRecordRow.workflow_id)
        .order_by(func.min(ResultLedgerRecordRow.id))
        .offset(offset)
        .limit(limit)
    ).all()
    entries: list[dict[str, Any]] = []
    for workflow_id in workflow_ids:
        result = read_validated_result_history(session, workflow_id)
        if result is None:
            raise ValueError("result history absent despite retained workflow index")
        entries.append(result)
    return {
        "results": entries,
        "total": total,
        "returned": len(entries),
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(entries) < total,
        "read_only": True,
        "payment_status_verified": False,
        "royalty_entitlement_verified": False,
        "limitations": [
            "These are stored outcomes and calculated shares, not proof of a royalty agreement.",
            "No payment receipts, disbursements, or outstanding balances are verified here.",
            "Only the validated latest revision is current; earlier values must not be summed.",
        ],
    }
