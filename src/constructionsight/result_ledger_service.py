"""Result ledger service."""

from __future__ import annotations

import hashlib
import json
from datetime import date

from constructionsight.lead_workflow_models import LeadWorkflowRecord
from constructionsight.result_ledger_models import (
    ResultLedgerRecord,
    ResultLedgerStatus,
    ResultShareRecord,
    ResultShareStatus,
)


def build_result_ledger_record(
    *,
    workflow: LeadWorkflowRecord,
    status: ResultLedgerStatus,
    decided_date: date | None = None,
    gross_value: float | None = None,
    share_rate: float | None = None,
    reasons: list[str] | None = None,
) -> ResultLedgerRecord:
    """Build an immutable content-addressed result row for a workflow."""

    normalized_reasons = reasons or []
    share = None
    share_status = ResultShareStatus.NOT_APPLICABLE
    limitations: list[str] = []
    if status == ResultLedgerStatus.WON:
        if gross_value is None:
            share_status = ResultShareStatus.PENDING_GROSS_VALUE
            limitations.append("gross value is missing")
        elif share_rate is None:
            share_status = ResultShareStatus.PENDING_SHARE_RATE
            limitations.append("share rate is missing")
        else:
            share_status = ResultShareStatus.CALCULATED
            share = _share_record(workflow.workflow_id, gross_value, share_rate)
    return ResultLedgerRecord(
        ledger_id=_ledger_id(
            workflow_id=workflow.workflow_id,
            package_id=workflow.package_id,
            status=status,
            decided_date=decided_date,
            gross_value=gross_value,
            share_rate=share_rate,
            reasons=normalized_reasons,
        ),
        workflow_id=workflow.workflow_id,
        package_id=workflow.package_id,
        status=status,
        decided_date=decided_date,
        gross_value=gross_value,
        share_status=share_status,
        share=share,
        reasons=normalized_reasons,
        limitations=limitations,
    )


def _share_record(
    workflow_id: str,
    gross_value: float,
    share_rate: float,
) -> ResultShareRecord:
    """Build a calculated share record."""

    share_value = round(gross_value * share_rate, 2)
    return ResultShareRecord(
        share_record_id=_share_id(workflow_id, gross_value, share_rate),
        workflow_id=workflow_id,
        gross_value=gross_value,
        share_rate=share_rate,
        share_value=share_value,
    )


def _ledger_id(
    *,
    workflow_id: str,
    package_id: str,
    status: ResultLedgerStatus,
    decided_date: date | None,
    gross_value: float | None,
    share_rate: float | None,
    reasons: list[str],
) -> str:
    """Build a deterministic identity over approval-significant result content."""

    payload = {
        "workflow_id": workflow_id,
        "package_id": package_id,
        "status": status.value,
        "decided_date": decided_date.isoformat() if decided_date else None,
        "gross_value": None if gross_value is None else round(gross_value, 2),
        "share_rate": None if share_rate is None else round(share_rate, 6),
        "reasons": sorted(reasons),
    }
    basis = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"result-ledger:{_short_hash(basis)}"


def _share_id(workflow_id: str, gross_value: float, share_rate: float) -> str:
    """Build deterministic share id."""

    basis = "|".join([workflow_id, f"{gross_value:.2f}", f"{share_rate:.4f}"])
    return f"result-share:{_short_hash(basis)}"


def _short_hash(value: str) -> str:
    """Return short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
