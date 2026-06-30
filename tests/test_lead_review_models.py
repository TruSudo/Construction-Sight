import pytest
from pydantic import ValidationError

from constructionsight.lead_review_models import (
    LeadReviewItem,
    LeadReviewPackage,
    LeadReviewStatus,
)


def test_ready_package_requires_items() -> None:
    with pytest.raises(ValidationError):
        LeadReviewPackage(
            package_id="lead-review:test",
            base_candidate_id="candidate:test",
            lead_score=80,
            status=LeadReviewStatus.READY,
            summary="ready",
        )


def test_ready_package_rejects_limitations() -> None:
    item = LeadReviewItem(
        item_key="lead-item:test",
        label="review",
        rationale="test",
    )

    with pytest.raises(ValidationError):
        LeadReviewPackage(
            package_id="lead-review:test",
            base_candidate_id="candidate:test",
            lead_score=80,
            status=LeadReviewStatus.READY,
            summary="ready",
            items=[item],
            limitations=["x"],
        )


def test_lead_review_package_rejects_duplicate_evidence_notes() -> None:
    with pytest.raises(ValidationError):
        LeadReviewPackage(
            package_id="lead-review:test",
            base_candidate_id="candidate:test",
            lead_score=10,
            status=LeadReviewStatus.MONITOR,
            summary="monitor",
            evidence_notes=["x", "x"],
        )


def test_lead_review_package_serializes() -> None:
    item = LeadReviewItem(
        item_key="lead-item:test",
        label="review",
        rationale="test",
    )
    package = LeadReviewPackage(
        package_id="lead-review:test",
        base_candidate_id="candidate:test",
        lead_score=80,
        status=LeadReviewStatus.READY,
        summary="ready",
        items=[item],
    )

    assert package.to_dict()["status"] == "ready"
