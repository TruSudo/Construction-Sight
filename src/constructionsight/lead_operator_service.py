"""Read-safe operator service for persisted post-enrichment lead records."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_operator_models import (
    LeadOperatorRecord,
    LeadOperatorRecordKind,
    LeadWorkflowTransitionReport,
)
from constructionsight.lead_workflow_models import LeadWorkflowRecord, LeadWorkflowStatus
from constructionsight.lead_workflow_service import transition_lead_workflow
from constructionsight.storage.lead_workflow_orm import (
    LeadDuplicateResultRecord,
    LeadFingerprintRecord,
    LeadReviewPackageRecord,
    LeadWorkflowEventRecord,
    LeadWorkflowRecordRow,
    OpportunityEnrichmentReportRecord,
    ResultLedgerRecordRow,
    ResultShareRecordRow,
)
from constructionsight.storage.lead_workflow_store import store_lead_workflow_record


class LeadOperatorError(ValueError):
    """Raised when operator data is absent, stale, malformed, or unsupported."""


_FILTER_SUPPORT: dict[LeadOperatorRecordKind, frozenset[str]] = {
    LeadOperatorRecordKind.ENRICHMENT: frozenset({"base_candidate_id"}),
    LeadOperatorRecordKind.REVIEW: frozenset({"status", "base_candidate_id"}),
    LeadOperatorRecordKind.FINGERPRINT: frozenset({"base_candidate_id"}),
    LeadOperatorRecordKind.DUPLICATE: frozenset({"status", "base_candidate_id"}),
    LeadOperatorRecordKind.WORKFLOW: frozenset(
        {"status", "base_candidate_id", "workflow_id"}
    ),
    LeadOperatorRecordKind.EVENT: frozenset({"status", "workflow_id"}),
    LeadOperatorRecordKind.LEDGER: frozenset({"status", "workflow_id"}),
    LeadOperatorRecordKind.SHARE: frozenset({"workflow_id"}),
}


def list_lead_operator_records(
    session: Session,
    record_kind: LeadOperatorRecordKind,
    *,
    limit: int = 100,
    status: str | None = None,
    base_candidate_id: str | None = None,
    workflow_id: str | None = None,
) -> list[LeadOperatorRecord]:
    """Return newest persisted records with explicit, kind-supported filters."""

    if limit < 1 or limit > 1000:
        raise LeadOperatorError("limit must be between 1 and 1000")
    _validate_filters(
        record_kind,
        status=status,
        base_candidate_id=base_candidate_id,
        workflow_id=workflow_id,
    )

    if record_kind == LeadOperatorRecordKind.ENRICHMENT:
        statement = select(OpportunityEnrichmentReportRecord)
        if base_candidate_id is not None:
            statement = statement.where(
                OpportunityEnrichmentReportRecord.base_candidate_id
                == base_candidate_id
            )
        rows = session.execute(
            statement.order_by(OpportunityEnrichmentReportRecord.id.desc()).limit(
                limit
            )
        ).scalars()
        return [_enrichment_record(row) for row in rows]

    if record_kind == LeadOperatorRecordKind.REVIEW:
        statement = select(LeadReviewPackageRecord)
        if status is not None:
            statement = statement.where(LeadReviewPackageRecord.status == status)
        if base_candidate_id is not None:
            statement = statement.where(
                LeadReviewPackageRecord.base_candidate_id == base_candidate_id
            )
        rows = session.execute(
            statement.order_by(LeadReviewPackageRecord.id.desc()).limit(limit)
        ).scalars()
        return [_review_record(row) for row in rows]

    if record_kind == LeadOperatorRecordKind.FINGERPRINT:
        statement = select(LeadFingerprintRecord)
        if base_candidate_id is not None:
            statement = statement.where(
                LeadFingerprintRecord.base_candidate_id == base_candidate_id
            )
        rows = session.execute(
            statement.order_by(LeadFingerprintRecord.id.desc()).limit(limit)
        ).scalars()
        return [_fingerprint_record(row) for row in rows]

    if record_kind == LeadOperatorRecordKind.DUPLICATE:
        statement = select(LeadDuplicateResultRecord)
        if status is not None:
            statement = statement.where(LeadDuplicateResultRecord.status == status)
        if base_candidate_id is not None:
            statement = statement.where(
                LeadDuplicateResultRecord.base_candidate_id == base_candidate_id
            )
        rows = session.execute(
            statement.order_by(LeadDuplicateResultRecord.id.desc()).limit(limit)
        ).scalars()
        return [_duplicate_record(row) for row in rows]

    if record_kind == LeadOperatorRecordKind.WORKFLOW:
        statement = select(LeadWorkflowRecordRow)
        if status is not None:
            statement = statement.where(LeadWorkflowRecordRow.status == status)
        if base_candidate_id is not None:
            statement = statement.where(
                LeadWorkflowRecordRow.base_candidate_id == base_candidate_id
            )
        if workflow_id is not None:
            statement = statement.where(
                LeadWorkflowRecordRow.workflow_id == workflow_id
            )
        rows = session.execute(
            statement.order_by(LeadWorkflowRecordRow.id.desc()).limit(limit)
        ).scalars()
        return [_workflow_record(row) for row in rows]

    if record_kind == LeadOperatorRecordKind.EVENT:
        statement = select(LeadWorkflowEventRecord)
        if status is not None:
            statement = statement.where(
                LeadWorkflowEventRecord.current_status == status
            )
        if workflow_id is not None:
            statement = statement.where(
                LeadWorkflowEventRecord.workflow_id == workflow_id
            )
        rows = session.execute(
            statement.order_by(LeadWorkflowEventRecord.id.desc()).limit(limit)
        ).scalars()
        return [_event_record(row) for row in rows]

    if record_kind == LeadOperatorRecordKind.LEDGER:
        statement = select(ResultLedgerRecordRow)
        if status is not None:
            statement = statement.where(ResultLedgerRecordRow.status == status)
        if workflow_id is not None:
            statement = statement.where(
                ResultLedgerRecordRow.workflow_id == workflow_id
            )
        rows = session.execute(
            statement.order_by(ResultLedgerRecordRow.id.desc()).limit(limit)
        ).scalars()
        return [_ledger_record(row) for row in rows]

    statement = select(ResultShareRecordRow)
    if workflow_id is not None:
        statement = statement.where(ResultShareRecordRow.workflow_id == workflow_id)
    rows = session.execute(
        statement.order_by(ResultShareRecordRow.id.desc()).limit(limit)
    ).scalars()
    return [_share_record(row) for row in rows]


def get_lead_operator_record(
    session: Session,
    record_kind: LeadOperatorRecordKind,
    record_id: str,
) -> LeadOperatorRecord | None:
    """Return one record by its canonical persisted identifier."""

    if record_kind == LeadOperatorRecordKind.ENRICHMENT:
        row = session.execute(
            select(OpportunityEnrichmentReportRecord).where(
                OpportunityEnrichmentReportRecord.report_id == record_id
            )
        ).scalar_one_or_none()
        return None if row is None else _enrichment_record(row)
    if record_kind == LeadOperatorRecordKind.REVIEW:
        row = session.execute(
            select(LeadReviewPackageRecord).where(
                LeadReviewPackageRecord.package_id == record_id
            )
        ).scalar_one_or_none()
        return None if row is None else _review_record(row)
    if record_kind == LeadOperatorRecordKind.FINGERPRINT:
        row = session.execute(
            select(LeadFingerprintRecord).where(
                LeadFingerprintRecord.fingerprint_key == record_id
            )
        ).scalar_one_or_none()
        return None if row is None else _fingerprint_record(row)
    if record_kind == LeadOperatorRecordKind.DUPLICATE:
        row = session.execute(
            select(LeadDuplicateResultRecord).where(
                LeadDuplicateResultRecord.result_id == record_id
            )
        ).scalar_one_or_none()
        return None if row is None else _duplicate_record(row)
    if record_kind == LeadOperatorRecordKind.WORKFLOW:
        row = _workflow_row(session, record_id)
        return None if row is None else _workflow_record(row)
    if record_kind == LeadOperatorRecordKind.EVENT:
        row = session.execute(
            select(LeadWorkflowEventRecord).where(
                LeadWorkflowEventRecord.event_id == record_id
            )
        ).scalar_one_or_none()
        return None if row is None else _event_record(row)
    if record_kind == LeadOperatorRecordKind.LEDGER:
        row = session.execute(
            select(ResultLedgerRecordRow).where(
                ResultLedgerRecordRow.ledger_id == record_id
            )
        ).scalar_one_or_none()
        return None if row is None else _ledger_record(row)
    row = session.execute(
        select(ResultShareRecordRow).where(
            ResultShareRecordRow.share_record_id == record_id
        )
    ).scalar_one_or_none()
    return None if row is None else _share_record(row)


def load_persisted_lead_workflow(
    session: Session,
    workflow_id: str,
) -> LeadWorkflowRecord:
    """Load and integrity-check one workflow before an operator mutation."""

    row = _workflow_row(session, workflow_id)
    if row is None:
        raise LeadOperatorError(f"lead workflow not found: {workflow_id}")
    payload = _decode_payload(
        row.payload_json,
        LeadOperatorRecordKind.WORKFLOW,
        workflow_id,
    )
    record = LeadWorkflowRecord.model_validate(payload)
    indexed_values: dict[str, object] = {
        "workflow_id": row.workflow_id,
        "package_id": row.package_id,
        "base_candidate_id": row.base_candidate_id,
        "fingerprint_key": row.fingerprint_key,
        "status": row.status,
        "lead_score": row.lead_score,
    }
    payload_values: dict[str, object] = {
        "workflow_id": record.workflow_id,
        "package_id": record.package_id,
        "base_candidate_id": record.base_candidate_id,
        "fingerprint_key": record.fingerprint_key,
        "status": record.status.value,
        "lead_score": record.lead_score,
    }
    drifted_fields = [
        field_name
        for field_name, indexed_value in indexed_values.items()
        if payload_values[field_name] != indexed_value
    ]
    if drifted_fields:
        fields = ", ".join(sorted(drifted_fields))
        raise LeadOperatorError(
            "lead workflow indexed fields disagree with payload for "
            f"{workflow_id}: {fields}"
        )
    event_ids = [event.event_id for event in record.events]
    if len(event_ids) != len(set(event_ids)):
        raise LeadOperatorError(
            f"lead workflow contains duplicate event ids: {workflow_id}"
        )
    return record


def transition_persisted_lead_workflow(
    session: Session,
    *,
    workflow_id: str,
    expected_current_status: LeadWorkflowStatus,
    next_status: LeadWorkflowStatus,
    reason: str,
) -> LeadWorkflowTransitionReport:
    """Apply one matrix-valid, stale-state-protected workflow transition."""

    normalized_reason = reason.strip()
    if not normalized_reason:
        raise LeadOperatorError("workflow transition reason must not be blank")
    record = load_persisted_lead_workflow(session, workflow_id)
    if record.status != expected_current_status:
        raise LeadOperatorError(
            "lead workflow current status does not match the operator expectation: "
            f"expected {expected_current_status.value}, "
            f"observed {record.status.value}"
        )
    updated = transition_lead_workflow(
        record=record,
        next_status=next_status,
        reason=normalized_reason,
    )
    store_lead_workflow_record(session, updated)
    session.flush()
    event = updated.events[-1]
    return LeadWorkflowTransitionReport(
        workflow_id=updated.workflow_id,
        previous_status=record.status.value,
        current_status=updated.status.value,
        event_id=event.event_id,
        reason=event.reason,
        event_count=len(updated.events),
        workflow_payload=updated.to_dict(),
    )


def _validate_filters(
    record_kind: LeadOperatorRecordKind,
    *,
    status: str | None,
    base_candidate_id: str | None,
    workflow_id: str | None,
) -> None:
    supported = _FILTER_SUPPORT[record_kind]
    filters = {
        "status": status,
        "base_candidate_id": base_candidate_id,
        "workflow_id": workflow_id,
    }
    unsupported = [
        filter_name
        for filter_name, filter_value in filters.items()
        if filter_value is not None and filter_name not in supported
    ]
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise LeadOperatorError(
            f"unsupported filter(s) for {record_kind.value} records: {names}"
        )


def _workflow_row(
    session: Session,
    workflow_id: str,
) -> LeadWorkflowRecordRow | None:
    return session.execute(
        select(LeadWorkflowRecordRow).where(
            LeadWorkflowRecordRow.workflow_id == workflow_id
        )
    ).scalar_one_or_none()


def _decode_payload(
    payload_json: str,
    record_kind: LeadOperatorRecordKind,
    record_id: str,
) -> dict[str, Any]:
    try:
        data: Any = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        raise LeadOperatorError(
            f"malformed {record_kind.value} payload JSON for record: {record_id}"
        ) from exc
    if not isinstance(data, dict):
        raise LeadOperatorError(
            f"{record_kind.value} payload must be a JSON object for record: "
            f"{record_id}"
        )
    return {str(key): value for key, value in data.items()}


def _enrichment_record(
    row: OpportunityEnrichmentReportRecord,
) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.ENRICHMENT,
        record_id=row.report_id,
        base_candidate_id=row.base_candidate_id,
        lead_score=row.lead_score,
        observed_created_at=row.observed_created_at,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.ENRICHMENT,
            row.report_id,
        ),
    )


def _review_record(row: LeadReviewPackageRecord) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.REVIEW,
        record_id=row.package_id,
        status=row.status,
        base_candidate_id=row.base_candidate_id,
        package_id=row.package_id,
        lead_score=row.lead_score,
        observed_created_at=row.observed_created_at,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.REVIEW,
            row.package_id,
        ),
    )


def _fingerprint_record(row: LeadFingerprintRecord) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.FINGERPRINT,
        record_id=row.fingerprint_key,
        base_candidate_id=row.base_candidate_id,
        lead_score=row.lead_score,
        observed_created_at=row.observed_created_at,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.FINGERPRINT,
            row.fingerprint_key,
        ),
    )


def _duplicate_record(row: LeadDuplicateResultRecord) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.DUPLICATE,
        record_id=row.result_id,
        status=row.status,
        base_candidate_id=row.base_candidate_id,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.DUPLICATE,
            row.result_id,
        ),
    )


def _workflow_record(row: LeadWorkflowRecordRow) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.WORKFLOW,
        record_id=row.workflow_id,
        status=row.status,
        base_candidate_id=row.base_candidate_id,
        workflow_id=row.workflow_id,
        package_id=row.package_id,
        lead_score=row.lead_score,
        observed_created_at=row.observed_created_at,
        observed_updated_at=row.observed_updated_at,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.WORKFLOW,
            row.workflow_id,
        ),
    )


def _event_record(row: LeadWorkflowEventRecord) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.EVENT,
        record_id=row.event_id,
        status=row.current_status,
        workflow_id=row.workflow_id,
        observed_created_at=row.observed_created_at,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.EVENT,
            row.event_id,
        ),
    )


def _ledger_record(row: ResultLedgerRecordRow) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.LEDGER,
        record_id=row.ledger_id,
        status=row.status,
        workflow_id=row.workflow_id,
        package_id=row.package_id,
        observed_created_at=row.observed_created_at,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.LEDGER,
            row.ledger_id,
        ),
    )


def _share_record(row: ResultShareRecordRow) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=LeadOperatorRecordKind.SHARE,
        record_id=row.share_record_id,
        workflow_id=row.workflow_id,
        payload=_decode_payload(
            row.payload_json,
            LeadOperatorRecordKind.SHARE,
            row.share_record_id,
        ),
    )
