"""Read-safe operator service for persisted post-enrichment lead records."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_dedupe_models import LeadDuplicateStatus
from constructionsight.lead_operator_models import (
    LeadOperatorRecord,
    LeadOperatorRecordKind,
    LeadWorkflowTransitionReport,
)
from constructionsight.lead_workflow_models import (
    ACTIONABLE_LEAD_WORKFLOW_STATUSES,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
    require_duplicate_review_clear,
)
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
from constructionsight.storage.lead_workflow_store import (
    compare_and_swap_lead_workflow_record,
    store_lead_workflow_record,
)


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
        enrichment_statement = select(OpportunityEnrichmentReportRecord)
        if base_candidate_id is not None:
            enrichment_statement = enrichment_statement.where(
                OpportunityEnrichmentReportRecord.base_candidate_id
                == base_candidate_id
            )
        enrichment_rows = session.execute(
            enrichment_statement.order_by(
                OpportunityEnrichmentReportRecord.id.desc()
            ).limit(limit)
        ).scalars()
        return [_enrichment_record(enrichment_row) for enrichment_row in enrichment_rows]

    if record_kind == LeadOperatorRecordKind.REVIEW:
        review_statement = select(LeadReviewPackageRecord)
        if status is not None:
            review_statement = review_statement.where(
                LeadReviewPackageRecord.status == status
            )
        if base_candidate_id is not None:
            review_statement = review_statement.where(
                LeadReviewPackageRecord.base_candidate_id == base_candidate_id
            )
        review_rows = session.execute(
            review_statement.order_by(LeadReviewPackageRecord.id.desc()).limit(limit)
        ).scalars()
        return [_review_record(review_row) for review_row in review_rows]

    if record_kind == LeadOperatorRecordKind.FINGERPRINT:
        fingerprint_statement = select(LeadFingerprintRecord)
        if base_candidate_id is not None:
            fingerprint_statement = fingerprint_statement.where(
                LeadFingerprintRecord.base_candidate_id == base_candidate_id
            )
        fingerprint_rows = session.execute(
            fingerprint_statement.order_by(LeadFingerprintRecord.id.desc()).limit(
                limit
            )
        ).scalars()
        return [
            _fingerprint_record(fingerprint_row)
            for fingerprint_row in fingerprint_rows
        ]

    if record_kind == LeadOperatorRecordKind.DUPLICATE:
        duplicate_statement = select(LeadDuplicateResultRecord)
        if status is not None:
            duplicate_statement = duplicate_statement.where(
                LeadDuplicateResultRecord.status == status
            )
        if base_candidate_id is not None:
            duplicate_statement = duplicate_statement.where(
                LeadDuplicateResultRecord.base_candidate_id == base_candidate_id
            )
        duplicate_rows = session.execute(
            duplicate_statement.order_by(LeadDuplicateResultRecord.id.desc()).limit(
                limit
            )
        ).scalars()
        return [_duplicate_record(duplicate_row) for duplicate_row in duplicate_rows]

    if record_kind == LeadOperatorRecordKind.WORKFLOW:
        workflow_statement = select(LeadWorkflowRecordRow)
        if status is not None:
            workflow_statement = workflow_statement.where(
                LeadWorkflowRecordRow.status == status
            )
        if base_candidate_id is not None:
            workflow_statement = workflow_statement.where(
                LeadWorkflowRecordRow.base_candidate_id == base_candidate_id
            )
        if workflow_id is not None:
            workflow_statement = workflow_statement.where(
                LeadWorkflowRecordRow.workflow_id == workflow_id
            )
        workflow_rows = session.execute(
            workflow_statement.order_by(LeadWorkflowRecordRow.id.desc()).limit(limit)
        ).scalars()
        return [_workflow_record(workflow_row) for workflow_row in workflow_rows]

    if record_kind == LeadOperatorRecordKind.EVENT:
        event_statement = select(LeadWorkflowEventRecord)
        if status is not None:
            event_statement = event_statement.where(
                LeadWorkflowEventRecord.current_status == status
            )
        if workflow_id is not None:
            event_statement = event_statement.where(
                LeadWorkflowEventRecord.workflow_id == workflow_id
            )
        event_rows = session.execute(
            event_statement.order_by(LeadWorkflowEventRecord.id.desc()).limit(limit)
        ).scalars()
        return [_event_record(event_row) for event_row in event_rows]

    if record_kind == LeadOperatorRecordKind.LEDGER:
        ledger_statement = select(ResultLedgerRecordRow)
        if status is not None:
            ledger_statement = ledger_statement.where(
                ResultLedgerRecordRow.status == status
            )
        if workflow_id is not None:
            ledger_statement = ledger_statement.where(
                ResultLedgerRecordRow.workflow_id == workflow_id
            )
        ledger_rows = session.execute(
            ledger_statement.order_by(ResultLedgerRecordRow.id.desc()).limit(limit)
        ).scalars()
        return [_ledger_record(ledger_row) for ledger_row in ledger_rows]

    share_statement = select(ResultShareRecordRow)
    if workflow_id is not None:
        share_statement = share_statement.where(
            ResultShareRecordRow.workflow_id == workflow_id
        )
    share_rows = session.execute(
        share_statement.order_by(ResultShareRecordRow.id.desc()).limit(limit)
    ).scalars()
    return [_share_record(share_row) for share_row in share_rows]


def get_lead_operator_record(
    session: Session,
    record_kind: LeadOperatorRecordKind,
    record_id: str,
) -> LeadOperatorRecord | None:
    """Return one record by its canonical persisted identifier."""

    if record_kind == LeadOperatorRecordKind.ENRICHMENT:
        enrichment_row = session.execute(
            select(OpportunityEnrichmentReportRecord).where(
                OpportunityEnrichmentReportRecord.report_id == record_id
            )
        ).scalar_one_or_none()
        return (
            None
            if enrichment_row is None
            else _enrichment_record(enrichment_row)
        )
    if record_kind == LeadOperatorRecordKind.REVIEW:
        review_row = session.execute(
            select(LeadReviewPackageRecord).where(
                LeadReviewPackageRecord.package_id == record_id
            )
        ).scalar_one_or_none()
        return None if review_row is None else _review_record(review_row)
    if record_kind == LeadOperatorRecordKind.FINGERPRINT:
        fingerprint_row = session.execute(
            select(LeadFingerprintRecord).where(
                LeadFingerprintRecord.fingerprint_key == record_id
            )
        ).scalar_one_or_none()
        return (
            None
            if fingerprint_row is None
            else _fingerprint_record(fingerprint_row)
        )
    if record_kind == LeadOperatorRecordKind.DUPLICATE:
        duplicate_row = session.execute(
            select(LeadDuplicateResultRecord).where(
                LeadDuplicateResultRecord.result_id == record_id
            )
        ).scalar_one_or_none()
        return None if duplicate_row is None else _duplicate_record(duplicate_row)
    if record_kind == LeadOperatorRecordKind.WORKFLOW:
        workflow_row = _workflow_row(session, record_id)
        return None if workflow_row is None else _workflow_record(workflow_row)
    if record_kind == LeadOperatorRecordKind.EVENT:
        event_row = session.execute(
            select(LeadWorkflowEventRecord).where(
                LeadWorkflowEventRecord.event_id == record_id
            )
        ).scalar_one_or_none()
        return None if event_row is None else _event_record(event_row)
    if record_kind == LeadOperatorRecordKind.LEDGER:
        ledger_row = session.execute(
            select(ResultLedgerRecordRow).where(
                ResultLedgerRecordRow.ledger_id == record_id
            )
        ).scalar_one_or_none()
        return None if ledger_row is None else _ledger_record(ledger_row)
    share_row = session.execute(
        select(ResultShareRecordRow).where(
            ResultShareRecordRow.share_record_id == record_id
        )
    ).scalar_one_or_none()
    return None if share_row is None else _share_record(share_row)


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


def require_persisted_duplicate_review_clear(
    session: Session, record: LeadWorkflowRecord, next_status: LeadWorkflowStatus,
) -> None:
    """Gate actionability against both workflow limits and durable dedupe results."""

    require_duplicate_review_clear(limitations=record.limitations, next_status=next_status)
    if next_status not in ACTIONABLE_LEAD_WORKFLOW_STATUSES:
        return
    unresolved_result = session.execute(
        select(LeadDuplicateResultRecord.result_id).where(
            LeadDuplicateResultRecord.base_candidate_id == record.base_candidate_id,
            LeadDuplicateResultRecord.status.in_(
                (LeadDuplicateStatus.DUPLICATE.value, LeadDuplicateStatus.REVIEW_NEEDED.value)
            ),
        ).limit(1)
    ).scalar_one_or_none()
    if unresolved_result is not None:
        raise LeadOperatorError(
            "unresolved duplicate review blocks actionable persisted lead workflow status"
        )


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
    require_persisted_duplicate_review_clear(session, record, next_status)
    updated = transition_lead_workflow(
        record=record,
        next_status=next_status,
        reason=normalized_reason,
    )
    try:
        compare_and_swap_lead_workflow_record(
            session,
            current=record,
            updated=updated,
        )
    except ValueError as exc:
        raise LeadOperatorError(str(exc)) from exc
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
