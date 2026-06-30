from constructionsight.lead_dedupe_models import (
    LeadDuplicateResult,
    LeadDuplicateStatus,
    LeadFingerprint,
)
from constructionsight.lead_review_models import (
    LeadReviewItem,
    LeadReviewPackage,
    LeadReviewStatus,
)
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_service import (
    create_lead_workflow,
    transition_lead_workflow,
)


def _package(status: LeadReviewStatus, score: int = 50) -> LeadReviewPackage:
    items = []
    if status == LeadReviewStatus.READY:
        items = [
            LeadReviewItem(
                item_key="lead-item:test",
                label="review package",
                rationale="test rationale",
            )
        ]
    return LeadReviewPackage(
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        lead_score=score,
        status=status,
        summary="test package",
        items=items,
    )


def _duplicate_result(status: LeadDuplicateStatus) -> LeadDuplicateResult:
    fingerprint = LeadFingerprint(
        fingerprint_key="lead-fingerprint:test",
        base_candidate_id="candidate:test",
        site_key="site:test",
    )
    matched = ["lead-fingerprint:old"] if status == LeadDuplicateStatus.DUPLICATE else []
    return LeadDuplicateResult(
        result_id="lead-duplicate:test",
        status=status,
        candidate=fingerprint,
        matched_fingerprint_keys=matched,
    )


def test_create_lead_workflow_ready_from_ready_package() -> None:
    record = create_lead_workflow(package=_package(LeadReviewStatus.READY, score=80))

    assert record.status == LeadWorkflowStatus.READY
    assert record.events[0].current_status == LeadWorkflowStatus.READY
    assert record.workflow_id.startswith("lead-workflow:")


def test_create_lead_workflow_holds_duplicate() -> None:
    record = create_lead_workflow(
        package=_package(LeadReviewStatus.READY, score=80),
        duplicate_result=_duplicate_result(LeadDuplicateStatus.DUPLICATE),
    )

    assert record.status == LeadWorkflowStatus.HOLD
    assert "lead fingerprint is a duplicate" in record.limitations


def test_create_lead_workflow_reviews_near_match() -> None:
    fingerprint = LeadFingerprint(
        fingerprint_key="lead-fingerprint:test",
        base_candidate_id="candidate:test",
        site_key="site:test",
    )
    duplicate_result = LeadDuplicateResult(
        result_id="lead-duplicate:test",
        status=LeadDuplicateStatus.REVIEW_NEEDED,
        candidate=fingerprint,
    )

    record = create_lead_workflow(
        package=_package(LeadReviewStatus.READY, score=80),
        duplicate_result=duplicate_result,
    )

    assert record.status == LeadWorkflowStatus.READY
    assert "lead fingerprint needs review" in record.limitations


def test_transition_lead_workflow_appends_event() -> None:
    record = create_lead_workflow(package=_package(LeadReviewStatus.MONITOR, score=20))

    updated = transition_lead_workflow(
        record=record,
        next_status=LeadWorkflowStatus.REVIEW,
        reason="more source evidence arrived",
    )

    assert updated.status == LeadWorkflowStatus.REVIEW
    assert len(updated.events) == 2
    assert updated.events[-1].previous_status == LeadWorkflowStatus.MONITOR
    assert updated.events[-1].current_status == LeadWorkflowStatus.REVIEW
