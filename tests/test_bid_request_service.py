from datetime import UTC, datetime

import pytest

from constructionsight.bid_request_models import (
    BidRequestChannel,
    BidRequestEvidence,
)
from constructionsight.bid_request_service import (
    BidRequestEvidenceError,
    build_persisted_bid_request_evidence,
)
from constructionsight.lead_dedupe_service import (
    build_lead_fingerprint,
    check_lead_duplicate,
)
from constructionsight.lead_review_models import (
    LeadReviewItem,
    LeadReviewPackage,
    LeadReviewStatus,
)
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_store import (
    store_lead_duplicate_result,
    store_lead_review_package,
    store_lead_workflow_record,
)


def _package(
    *,
    status: LeadReviewStatus = LeadReviewStatus.READY,
    score: int = 85,
) -> LeadReviewPackage:
    items = []
    if status is LeadReviewStatus.READY:
        items = [
            LeadReviewItem(
                item_key="lead-item:bid-request",
                label="prepare reviewed lead package",
                rationale="retained evidence supports request review",
            )
        ]
    return LeadReviewPackage(
        package_id=f"lead-review:bid-request:{status.value}",
        base_candidate_id="candidate:bid-request",
        lead_score=score,
        status=status,
        summary="bid request evidence test package",
        items=items,
        evidence_notes=["permit_transition: permit issued"],
    )


def _build(session, workflow_id: str, status: LeadWorkflowStatus) -> BidRequestEvidence:
    return build_persisted_bid_request_evidence(
        session,
        workflow_id=workflow_id,
        expected_current_status=status,
        request_channel=BidRequestChannel.EMAIL,
        requester_business_name="Example Contractor LLC",
        requester_business_role="estimating department",
        request_source_name="retained business email",
        request_source_reference="message:fixture:bid-request",
        request_review_basis="Reviewed the retained request and identified explicit pricing language.",
        request_observed_at=datetime(2026, 10, 8, 8, 30, tzinfo=UTC),
        request_text="Please send pricing for construction site security coverage.",
        scope_summary="Night security coverage for the reviewed construction site.",
    )


def test_ready_workflow_builds_content_bound_bid_request_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        first = _build(session, workflow.workflow_id, LeadWorkflowStatus.READY)
        second = _build(session, workflow.workflow_id, LeadWorkflowStatus.READY)

    assert first.request_evidence_id == second.request_evidence_id
    assert first.workflow_id == workflow.workflow_id
    assert first.requires_commercial_approval is True
    assert first.pricing_authorized is False
    assert first.bid_preparation_authorized is False
    assert first.bid_submission_authorized is False
    assert first.evidence_notes == ["permit_transition: permit issued"]


def test_non_ready_workflow_cannot_build_bid_request_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package(status=LeadReviewStatus.MONITOR, score=20)
    workflow = create_lead_workflow(package=package)

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        with pytest.raises(
            BidRequestEvidenceError,
            match="requires a ready or active lead workflow",
        ):
            _build(session, workflow.workflow_id, LeadWorkflowStatus.MONITOR)


def test_late_duplicate_finding_blocks_bid_request_evidence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)
    package = _package()
    workflow = create_lead_workflow(package=package)
    candidate = build_lead_fingerprint(package=package, site_key="site:bid-request")
    existing = candidate.model_copy(update={"base_candidate_id": "candidate:existing"})
    duplicate = check_lead_duplicate(candidate, [existing])

    with managed_session(factory) as session:
        store_lead_review_package(session, package)
        store_lead_workflow_record(session, workflow)
        store_lead_duplicate_result(session, duplicate)
        with pytest.raises(
            BidRequestEvidenceError,
            match="unresolved duplicate review",
        ):
            _build(session, workflow.workflow_id, LeadWorkflowStatus.READY)


def test_bid_request_evidence_requires_aware_observed_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        BidRequestEvidence(
            workflow_id="workflow:test",
            package_id="package:test",
            base_candidate_id="candidate:test",
            workflow_status="ready",
            request_channel=BidRequestChannel.EMAIL,
            requester_business_name="Example Contractor LLC",
            requester_business_role="estimating department",
            request_source_name="retained email",
            request_source_reference="message:test",
            request_review_basis="Reviewed explicit pricing request.",
            request_observed_at=datetime(2026, 10, 8, 8, 30),
            request_text="Please send a bid.",
            scope_summary="Night security coverage.",
        )
