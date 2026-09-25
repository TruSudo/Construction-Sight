"""Store helpers for post-enrichment lead workflow records."""

from __future__ import annotations

import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from constructionsight.lead_dedupe_models import (
    LeadDuplicateResult,
    LeadDuplicateStatus,
    LeadFingerprint,
)
from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.lead_workflow_models import (
    ACTIONABLE_LEAD_WORKFLOW_STATUSES,
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    require_duplicate_review_clear,
)
from constructionsight.opportunity_enrichment_models import OpportunityEnrichmentReport
from constructionsight.result_ledger_models import ResultLedgerRecord, ResultShareRecord
from constructionsight.result_ledger_service import validate_result_ledger_history
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


def store_opportunity_enrichment_report(
    session: Session,
    report: OpportunityEnrichmentReport,
) -> OpportunityEnrichmentReportRecord:
    """Insert or update an opportunity enrichment report."""

    session.flush()
    payload_json = _payload_json(report.to_dict())
    existing = session.execute(
        select(OpportunityEnrichmentReportRecord).where(
            OpportunityEnrichmentReportRecord.report_id == report.report_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = OpportunityEnrichmentReportRecord(
            report_id=report.report_id,
            base_candidate_id=report.base_candidate_id,
            lead_score=report.lead_score,
            confidence_score=report.confidence_score,
            confidence_band=report.confidence_band.value,
            scoring_profile_key=report.scoring_profile_key,
            scoring_profile_version=report.scoring_profile_version,
            next_action=report.next_action,
            observed_created_at=report.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.base_candidate_id = report.base_candidate_id
    existing.lead_score = report.lead_score
    existing.confidence_score = report.confidence_score
    existing.confidence_band = report.confidence_band.value
    existing.scoring_profile_key = report.scoring_profile_key
    existing.scoring_profile_version = report.scoring_profile_version
    existing.next_action = report.next_action
    existing.observed_created_at = report.created_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_lead_review_package(
    session: Session,
    package: LeadReviewPackage,
) -> LeadReviewPackageRecord:
    """Insert or update a lead review package."""

    session.flush()
    payload_json = _payload_json(package.to_dict())
    existing = session.execute(
        select(LeadReviewPackageRecord).where(
            LeadReviewPackageRecord.package_id == package.package_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = LeadReviewPackageRecord(
            package_id=package.package_id,
            base_candidate_id=package.base_candidate_id,
            lead_score=package.lead_score,
            status=package.status.value,
            observed_created_at=package.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.base_candidate_id = package.base_candidate_id
    existing.lead_score = package.lead_score
    existing.status = package.status.value
    existing.observed_created_at = package.created_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_lead_fingerprint(
    session: Session,
    fingerprint: LeadFingerprint,
) -> LeadFingerprintRecord:
    """Insert or update a lead fingerprint."""

    session.flush()
    payload_json = _payload_json(fingerprint.model_dump(mode="json"))
    existing = session.execute(
        select(LeadFingerprintRecord).where(
            LeadFingerprintRecord.fingerprint_key == fingerprint.fingerprint_key
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = LeadFingerprintRecord(
            fingerprint_key=fingerprint.fingerprint_key,
            base_candidate_id=fingerprint.base_candidate_id,
            site_key=fingerprint.site_key,
            source_key=fingerprint.source_key,
            source_record_id=fingerprint.source_record_id,
            normalized_title=fingerprint.normalized_title,
            lead_score=fingerprint.lead_score,
            observed_created_at=fingerprint.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.base_candidate_id = fingerprint.base_candidate_id
    existing.site_key = fingerprint.site_key
    existing.source_key = fingerprint.source_key
    existing.source_record_id = fingerprint.source_record_id
    existing.normalized_title = fingerprint.normalized_title
    existing.lead_score = fingerprint.lead_score
    existing.observed_created_at = fingerprint.created_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_lead_duplicate_result(
    session: Session,
    result: LeadDuplicateResult,
) -> LeadDuplicateResultRecord:
    """Insert a durable duplicate verdict or replay the same semantic decision."""

    session.flush()
    payload_json = _payload_json(result.to_dict())
    existing = session.execute(
        select(LeadDuplicateResultRecord).where(
            LeadDuplicateResultRecord.result_id == result.result_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = LeadDuplicateResultRecord(
            result_id=result.result_id,
            status=result.status.value,
            candidate_fingerprint_key=result.candidate.fingerprint_key,
            base_candidate_id=result.candidate.base_candidate_id,
            matched_count=len(result.matched_fingerprint_keys),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    if not _duplicate_result_replay_matches(existing, result, payload_json):
        raise ValueError("persisted lead duplicate results are immutable")
    return existing


def store_lead_workflow_event(
    session: Session,
    event: LeadWorkflowEvent,
    workflow_id: str | None = None,
) -> LeadWorkflowEventRecord:
    """Append one immutable workflow event or accept an exact replay."""

    session.flush()
    payload_json = _payload_json(event.model_dump(mode="json"))
    existing = session.execute(
        select(LeadWorkflowEventRecord).where(
            LeadWorkflowEventRecord.event_id == event.event_id
        )
    ).scalar_one_or_none()
    previous_status = event.previous_status.value if event.previous_status else None
    if existing is None:
        existing = LeadWorkflowEventRecord(
            event_id=event.event_id,
            workflow_id=workflow_id,
            previous_status=previous_status,
            current_status=event.current_status.value,
            reason=event.reason,
            observed_created_at=event.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    if (
        existing.workflow_id != workflow_id
        or existing.previous_status != previous_status
        or existing.current_status != event.current_status.value
        or existing.reason != event.reason
        or existing.observed_created_at != event.created_at.isoformat()
        or existing.payload_json != payload_json
    ):
        raise ValueError("persisted lead workflow events are immutable")
    return existing


def store_lead_workflow_record(
    session: Session,
    workflow: LeadWorkflowRecord,
) -> LeadWorkflowRecordRow:
    """Insert or update a lead workflow record and its events."""

    session.flush()
    require_duplicate_review_clear(
        limitations=workflow.limitations, next_status=workflow.status,
    )
    if workflow.status in ACTIONABLE_LEAD_WORKFLOW_STATUSES:
        unresolved_result = session.execute(
            select(LeadDuplicateResultRecord.result_id).where(
                LeadDuplicateResultRecord.base_candidate_id == workflow.base_candidate_id,
                LeadDuplicateResultRecord.status.in_(
                    (LeadDuplicateStatus.DUPLICATE.value, LeadDuplicateStatus.REVIEW_NEEDED.value)
                ),
            ).limit(1)
        ).scalar_one_or_none()
        if unresolved_result is not None:
            raise ValueError(
                "unresolved duplicate review blocks actionable persisted lead workflow status"
            )
    payload_json = _payload_json(workflow.to_dict())
    existing = session.execute(
        select(LeadWorkflowRecordRow).where(
            LeadWorkflowRecordRow.workflow_id == workflow.workflow_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = LeadWorkflowRecordRow(
            workflow_id=workflow.workflow_id,
            package_id=workflow.package_id,
            base_candidate_id=workflow.base_candidate_id,
            fingerprint_key=workflow.fingerprint_key,
            status=workflow.status.value,
            lead_score=workflow.lead_score,
            observed_created_at=workflow.created_at.isoformat(),
            observed_updated_at=workflow.updated_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
    else:
        existing.package_id = workflow.package_id
        existing.base_candidate_id = workflow.base_candidate_id
        existing.fingerprint_key = workflow.fingerprint_key
        existing.status = workflow.status.value
        existing.lead_score = workflow.lead_score
        existing.observed_created_at = workflow.created_at.isoformat()
        existing.observed_updated_at = workflow.updated_at.isoformat()
        existing.payload_json = payload_json
    for event in workflow.events:
        store_lead_workflow_event(session, event, workflow_id=workflow.workflow_id)
    return existing


def compare_and_swap_lead_workflow_record(
    session: Session,
    *,
    current: LeadWorkflowRecord,
    updated: LeadWorkflowRecord,
) -> LeadWorkflowRecordRow:
    """Atomically replace one exact projection and append exactly one new event."""

    if current.workflow_id != updated.workflow_id:
        raise ValueError("lead workflow compare-and-swap cannot change workflow identity")
    if len(updated.events) != len(current.events) + 1:
        raise ValueError("lead workflow compare-and-swap requires exactly one appended event")
    if updated.events[:-1] != current.events:
        raise ValueError("lead workflow compare-and-swap cannot rewrite historical events")
    require_duplicate_review_clear(
        limitations=updated.limitations,
        next_status=updated.status,
    )
    current_payload = _payload_json(current.to_dict())
    updated_payload = _payload_json(updated.to_dict())
    result = session.execute(
        update(LeadWorkflowRecordRow)
        .where(
            LeadWorkflowRecordRow.workflow_id == current.workflow_id,
            LeadWorkflowRecordRow.status == current.status.value,
            LeadWorkflowRecordRow.payload_json == current_payload,
        )
        .values(
            package_id=updated.package_id,
            base_candidate_id=updated.base_candidate_id,
            fingerprint_key=updated.fingerprint_key,
            status=updated.status.value,
            lead_score=updated.lead_score,
            observed_created_at=updated.created_at.isoformat(),
            observed_updated_at=updated.updated_at.isoformat(),
            payload_json=updated_payload,
        )
    )
    if result.rowcount != 1:
        raise ValueError(
            "lead workflow compare-and-swap rejected a stale or competing writer"
        )
    store_lead_workflow_event(
        session,
        updated.events[-1],
        workflow_id=updated.workflow_id,
    )
    session.flush()
    row = session.execute(
        select(LeadWorkflowRecordRow).where(
            LeadWorkflowRecordRow.workflow_id == updated.workflow_id
        )
    ).scalar_one()
    if row.payload_json != updated_payload:
        raise ValueError("lead workflow compare-and-swap did not persist the exact update")
    return row


def store_result_share_record(
    session: Session,
    share: ResultShareRecord,
) -> ResultShareRecordRow:
    """Insert an immutable calculated result share record."""

    session.flush()
    payload_json = _payload_json(share.model_dump(mode="json"))
    existing = session.execute(
        select(ResultShareRecordRow).where(
            ResultShareRecordRow.share_record_id == share.share_record_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.payload_json != payload_json:
            raise ValueError("persisted result share records are immutable")
        return existing
    existing = ResultShareRecordRow(
        share_record_id=share.share_record_id,
        workflow_id=share.workflow_id,
        gross_value=share.gross_value,
        share_rate=share.share_rate,
        share_value=share.share_value,
        payload_json=payload_json,
    )
    session.add(existing)
    return existing


def store_result_ledger_record(
    session: Session,
    ledger: ResultLedgerRecord,
) -> ResultLedgerRecordRow:
    """Append one validated immutable result ledger revision and optional share."""

    session.flush()
    payload_json = _payload_json(ledger.to_dict())
    existing = session.execute(
        select(ResultLedgerRecordRow).where(ResultLedgerRecordRow.ledger_id == ledger.ledger_id)
    ).scalar_one_or_none()
    if existing is not None:
        if existing.payload_json != payload_json:
            raise ValueError("persisted result ledger revisions are immutable")
        return existing

    history_rows = session.execute(
        select(ResultLedgerRecordRow).where(ResultLedgerRecordRow.workflow_id == ledger.workflow_id)
    ).scalars()
    history = [
        ResultLedgerRecord.model_validate(json.loads(row.payload_json)) for row in history_rows
    ]
    validate_result_ledger_history([*history, ledger])

    share_record_id = ledger.share.share_record_id if ledger.share else None
    decided_date = ledger.decided_date.isoformat() if ledger.decided_date else None
    row = ResultLedgerRecordRow(
        ledger_id=ledger.ledger_id,
        workflow_id=ledger.workflow_id,
        package_id=ledger.package_id,
        status=ledger.status.value,
        decided_date=decided_date,
        gross_value=ledger.gross_value,
        share_status=ledger.share_status.value,
        share_record_id=share_record_id,
        observed_created_at=ledger.created_at.isoformat(),
        payload_json=payload_json,
    )
    session.add(row)
    if ledger.share is not None:
        store_result_share_record(session, ledger.share)
    return row


def _duplicate_result_replay_matches(
    existing: LeadDuplicateResultRecord, result: LeadDuplicateResult, payload_json: str,
) -> bool:
    """Compare one verdict while ignoring non-decisional re-scan metadata."""

    if (
        existing.status != result.status.value
        or existing.base_candidate_id != result.candidate.base_candidate_id
        or existing.candidate_fingerprint_key != result.candidate.fingerprint_key
        or existing.matched_count != len(result.matched_fingerprint_keys)
    ):
        return False
    return _duplicate_decision_identity(existing.payload_json) == _duplicate_decision_identity(
        payload_json
    )


def _duplicate_decision_identity(payload_json: str) -> dict[str, object]:
    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        raise ValueError("persisted duplicate result must be a JSON object")
    candidate = payload.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("persisted duplicate result candidate must be an object")
    # Repeated checks can observe a new fingerprint creation timestamp and score
    # without changing the actual duplicate decision. Preserve the first receipt.
    candidate.pop("created_at", None)
    candidate.pop("lead_score", None)
    for field in ("matched_fingerprint_keys", "reasons", "limitations"):
        values = payload.get(field)
        if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
            raise ValueError("persisted duplicate result has malformed decision lists")
        payload[field] = sorted(values)
    return payload


def _payload_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON payload."""

    return json.dumps(payload, sort_keys=True)
