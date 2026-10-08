"""Build request-evidence packets from exact persisted commercial workflow state."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.bid_request_models import (
    BidRequestChannel,
    BidRequestEvidence,
)
from constructionsight.lead_operator_service import (
    LeadOperatorError,
    load_persisted_lead_workflow,
    require_persisted_duplicate_review_clear,
)
from constructionsight.lead_review_models import LeadReviewPackage, LeadReviewStatus
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.storage.lead_workflow_orm import LeadReviewPackageRecord


class BidRequestEvidenceError(ValueError):
    """Raised when persisted state does not support request-driven bid evidence."""


_REQUEST_ELIGIBLE_STATUSES = frozenset(
    {
        LeadWorkflowStatus.READY,
        LeadWorkflowStatus.ACTIVE,
    }
)


def build_persisted_bid_request_evidence(
    session: Session,
    *,
    workflow_id: str,
    expected_current_status: LeadWorkflowStatus,
    request_channel: BidRequestChannel,
    requester_business_name: str,
    requester_business_role: str,
    request_source_name: str,
    request_source_reference: str,
    request_review_basis: str,
    request_observed_at: datetime,
    request_text: str,
    scope_summary: str,
) -> BidRequestEvidence:
    """Build no-price, no-preparation, no-submission request evidence."""

    try:
        workflow = load_persisted_lead_workflow(session, workflow_id)
    except LeadOperatorError as exc:
        raise BidRequestEvidenceError(str(exc)) from exc

    if workflow.status is not expected_current_status:
        raise BidRequestEvidenceError(
            "lead workflow current status does not match bid-request expectation: "
            f"expected {expected_current_status.value}, observed {workflow.status.value}"
        )
    if workflow.status not in _REQUEST_ELIGIBLE_STATUSES:
        raise BidRequestEvidenceError(
            "bid request evidence requires a ready or active lead workflow"
        )
    if workflow.limitations:
        raise BidRequestEvidenceError(
            "bid request evidence is blocked by unresolved workflow limitations"
        )
    try:
        require_persisted_duplicate_review_clear(
            session,
            workflow,
            workflow.status,
        )
    except (LeadOperatorError, ValueError) as exc:
        raise BidRequestEvidenceError(str(exc)) from exc

    package = _load_review_package(session, workflow.package_id)
    if package.base_candidate_id != workflow.base_candidate_id:
        raise BidRequestEvidenceError(
            "lead review package candidate identity disagrees with workflow"
        )
    if package.status is not LeadReviewStatus.READY or package.limitations:
        raise BidRequestEvidenceError(
            "bid request evidence requires a ready review package without limitations"
        )

    return BidRequestEvidence(
        workflow_id=workflow.workflow_id,
        package_id=package.package_id,
        base_candidate_id=workflow.base_candidate_id,
        workflow_status=workflow.status.value,
        request_channel=request_channel,
        requester_business_name=requester_business_name,
        requester_business_role=requester_business_role,
        request_source_name=request_source_name,
        request_source_reference=request_source_reference,
        request_review_basis=request_review_basis,
        request_observed_at=request_observed_at,
        request_text=request_text,
        scope_summary=scope_summary,
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
        raise BidRequestEvidenceError(
            f"lead review package not found: {package_id}"
        )
    try:
        payload = json.loads(row.payload_json)
        package = LeadReviewPackage.model_validate(payload)
    except (json.JSONDecodeError, ValueError) as exc:
        raise BidRequestEvidenceError(
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
        raise BidRequestEvidenceError(
            "lead review package indexed fields disagree with payload: "
            f"{package_id}"
        )
    return package
