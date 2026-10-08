"""Governed outreach-preview construction from persisted lead state."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_operator_service import (
    LeadOperatorError,
    load_persisted_lead_workflow,
    require_persisted_duplicate_review_clear,
)
from constructionsight.lead_review_models import LeadReviewPackage, LeadReviewStatus
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.outreach_preview_models import (
    OutreachContactReference,
    OutreachPreview,
)
from constructionsight.storage.lead_workflow_orm import LeadReviewPackageRecord


class OutreachPreviewError(ValueError):
    """Raised when persisted state does not support an outreach preview."""


_PREVIEWABLE_WORKFLOW_STATUSES = frozenset(
    {
        LeadWorkflowStatus.READY,
        LeadWorkflowStatus.ACTIVE,
    }
)


def build_persisted_outreach_preview(
    session: Session,
    *,
    workflow_id: str,
    expected_current_status: LeadWorkflowStatus,
    contact: OutreachContactReference,
    subject: str,
    body: str,
) -> OutreachPreview:
    """Build a no-send outreach preview from exact persisted lead authority."""

    try:
        workflow = load_persisted_lead_workflow(session, workflow_id)
    except LeadOperatorError as exc:
        raise OutreachPreviewError(str(exc)) from exc

    if workflow.status != expected_current_status:
        raise OutreachPreviewError(
            "lead workflow current status does not match preview expectation: "
            f"expected {expected_current_status.value}, observed {workflow.status.value}"
        )
    if workflow.status not in _PREVIEWABLE_WORKFLOW_STATUSES:
        raise OutreachPreviewError(
            "outreach preview requires a ready or active lead workflow"
        )
    if workflow.limitations:
        raise OutreachPreviewError(
            "outreach preview is blocked by unresolved workflow limitations"
        )
    try:
        require_persisted_duplicate_review_clear(
            session,
            workflow,
            workflow.status,
        )
    except (LeadOperatorError, ValueError) as exc:
        raise OutreachPreviewError(str(exc)) from exc

    package = _load_review_package(session, workflow.package_id)
    if package.base_candidate_id != workflow.base_candidate_id:
        raise OutreachPreviewError(
            "lead review package candidate identity disagrees with workflow"
        )
    if package.status is not LeadReviewStatus.READY or package.limitations:
        raise OutreachPreviewError(
            "outreach preview requires a ready review package without limitations"
        )
    if not contact.operator_confirmed_business_contact:
        raise OutreachPreviewError(
            "operator confirmation of the business contact source is required"
        )
    if not subject.strip():
        raise OutreachPreviewError("outreach preview subject must not be blank")
    if not body.strip():
        raise OutreachPreviewError("outreach preview body must not be blank")

    return OutreachPreview(
        workflow_id=workflow.workflow_id,
        package_id=package.package_id,
        base_candidate_id=workflow.base_candidate_id,
        workflow_status=workflow.status.value,
        contact=contact,
        subject=subject,
        body=body,
        evidence_notes=list(package.evidence_notes),
    )


def _load_review_package(session: Session, package_id: str) -> LeadReviewPackage:
    """Load and integrity-check the exact persisted review package."""

    row = session.scalar(
        select(LeadReviewPackageRecord).where(
            LeadReviewPackageRecord.package_id == package_id
        )
    )
    if row is None:
        raise OutreachPreviewError(f"lead review package not found: {package_id}")
    try:
        payload = json.loads(row.payload_json)
        package = LeadReviewPackage.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise OutreachPreviewError(
            f"invalid persisted lead review package: {package_id}"
        ) from exc

    indexed = (
        row.package_id,
        row.base_candidate_id,
        row.lead_score,
        row.status,
        row.observed_created_at,
    )
    payload_values = (
        package.package_id,
        package.base_candidate_id,
        package.lead_score,
        package.status.value,
        package.created_at.isoformat(),
    )
    if indexed != payload_values:
        raise OutreachPreviewError(
            f"lead review package indexed fields disagree with payload: {package_id}"
        )
    return package
