"""Read-only, revision-aware result and share inspection for the local operator.

A calculated result share is not evidence of royalty entitlement or payment.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.result_ledger_models import ResultLedgerRecord
from constructionsight.result_ledger_service import validate_result_ledger_history
from constructionsight.storage.lead_workflow_orm import (
    LeadWorkflowRecordRow,
    ResultLedgerRecordRow,
    ResultShareRecordRow,
)

MAX_REVISIONS_PER_WORKFLOW = 100


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
        rows = session.scalars(
            select(ResultLedgerRecordRow)
            .where(ResultLedgerRecordRow.workflow_id == workflow_id)
            .order_by(ResultLedgerRecordRow.id)
            .limit(MAX_REVISIONS_PER_WORKFLOW + 1)
        ).all()
        if not rows or len(rows) > MAX_REVISIONS_PER_WORKFLOW:
            raise ValueError("result history absent or exceeds the inspection limit")
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
            history.append(record)
        current = validate_result_ledger_history(history)
        workflow = session.scalar(
            select(LeadWorkflowRecordRow)
            .where(LeadWorkflowRecordRow.workflow_id == workflow_id)
        )
        if workflow is None or workflow.package_id != current.package_id:
            raise ValueError("result ledger references missing or inconsistent workflow")
        if current.share is not None:
            share = current.share
            stored_share = session.scalar(
                select(ResultShareRecordRow)
                .where(ResultShareRecordRow.share_record_id == share.share_record_id)
            )
            if (
                stored_share is None
                or stored_share.workflow_id != workflow_id
                or stored_share.gross_value != share.gross_value
                or stored_share.share_rate != share.share_rate
                or stored_share.share_value != share.share_value
                or json.loads(stored_share.payload_json) != share.model_dump(mode="json")
            ):
                raise ValueError("result share and retained calculation disagree")
        entries.append({
            "workflow_id": workflow_id,
            "package_id": current.package_id,
            "current": current.to_dict(),
            "revision_count": len(history),
            "history": [record.to_dict() for record in history],
        })
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
