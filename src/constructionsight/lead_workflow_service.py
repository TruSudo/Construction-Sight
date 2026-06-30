"""Lead workflow status service."""

from __future__ import annotations

import hashlib

from constructionsight.lead_dedupe_models import LeadDuplicateResult, LeadDuplicateStatus
from constructionsight.lead_review_models import LeadReviewPackage, LeadReviewStatus
from constructionsight.lead_workflow_models import (
    LeadWorkflowEvent,
    LeadWorkflowRecord,
    LeadWorkflowStatus,
)


def create_lead_workflow(
    *,
    package: LeadReviewPackage,
    duplicate_result: LeadDuplicateResult | None = None,
) -> LeadWorkflowRecord:
    """Create a lead workflow record from review and dedupe results."""

    status = _initial_status(package, duplicate_result)
    limitations = list(package.limitations)
    notes: list[str] = []
    fingerprint_key = None
    if duplicate_result is not None:
        fingerprint_key = duplicate_result.candidate.fingerprint_key
        if duplicate_result.status == LeadDuplicateStatus.DUPLICATE:
            limitations.append("lead fingerprint is a duplicate")
        elif duplicate_result.status == LeadDuplicateStatus.REVIEW_NEEDED:
            limitations.append("lead fingerprint needs review")
    event = _event(
        workflow_id_basis=package.package_id,
        previous_status=None,
        current_status=status,
        reason="workflow created from lead review package",
    )
    return LeadWorkflowRecord(
        workflow_id=_workflow_id(package.package_id, fingerprint_key),
        package_id=package.package_id,
        base_candidate_id=package.base_candidate_id,
        fingerprint_key=fingerprint_key,
        status=status,
        lead_score=package.lead_score,
        events=[event],
        notes=notes,
        limitations=_unique(limitations),
    )


def transition_lead_workflow(
    *,
    record: LeadWorkflowRecord,
    next_status: LeadWorkflowStatus,
    reason: str,
) -> LeadWorkflowRecord:
    """Return a new workflow record with an appended status event."""

    event = _event(
        workflow_id_basis=record.workflow_id,
        previous_status=record.status,
        current_status=next_status,
        reason=reason,
    )
    return LeadWorkflowRecord(
        workflow_id=record.workflow_id,
        package_id=record.package_id,
        base_candidate_id=record.base_candidate_id,
        fingerprint_key=record.fingerprint_key,
        status=next_status,
        lead_score=record.lead_score,
        events=[*record.events, event],
        notes=list(record.notes),
        limitations=list(record.limitations),
        created_at=record.created_at,
    )


def _initial_status(
    package: LeadReviewPackage,
    duplicate_result: LeadDuplicateResult | None,
) -> LeadWorkflowStatus:
    """Return initial workflow status."""

    duplicate = (
        duplicate_result is not None
        and duplicate_result.status == LeadDuplicateStatus.DUPLICATE
    )
    if duplicate:
        return LeadWorkflowStatus.HOLD
    if package.status == LeadReviewStatus.HOLD:
        return LeadWorkflowStatus.HOLD
    if package.status == LeadReviewStatus.MONITOR:
        return LeadWorkflowStatus.MONITOR
    if package.status == LeadReviewStatus.REVIEW_REQUIRED:
        return LeadWorkflowStatus.REVIEW
    return LeadWorkflowStatus.READY


def _workflow_id(package_id: str, fingerprint_key: str | None) -> str:
    """Build deterministic workflow id."""

    basis = "|".join([package_id, fingerprint_key or ""])
    return f"lead-workflow:{_short_hash(basis)}"


def _event(
    *,
    workflow_id_basis: str,
    previous_status: LeadWorkflowStatus | None,
    current_status: LeadWorkflowStatus,
    reason: str,
) -> LeadWorkflowEvent:
    """Build deterministic workflow event."""

    previous_value = previous_status.value if previous_status else ""
    basis = "|".join([workflow_id_basis, previous_value, current_status.value, reason])
    return LeadWorkflowEvent(
        event_id=f"lead-workflow-event:{_short_hash(basis)}",
        previous_status=previous_status,
        current_status=current_status,
        reason=reason,
    )


def _short_hash(value: str) -> str:
    """Return short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _unique(values: list[str]) -> list[str]:
    """Return values with duplicates removed in first-seen order."""

    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
