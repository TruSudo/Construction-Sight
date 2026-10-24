"""Integrity-check one historical review package for exact original source lineage.

An indexed status is not trustworthy unless it agrees with the retained
package. This inspection neither reviews a new project nor grants authority.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.storage.lead_workflow_orm import LeadReviewPackageRecord


def verified_original_review_package(
    session: Session, *, package_id: str, candidate_key: str,
) -> LeadReviewPackage:
    """Fail closed on absent, altered, or cross-candidate historical reviews."""

    row = session.scalar(
        select(LeadReviewPackageRecord).where(
            LeadReviewPackageRecord.package_id == package_id
        )
    )
    if row is None:
        raise ValueError("original workflow review package is missing")
    try:
        review = LeadReviewPackage.model_validate_json(row.payload_json)
    except ValueError as exc:
        raise ValueError("original workflow review package payload is invalid") from exc
    indexed = (
        row.package_id,
        row.base_candidate_id,
        row.lead_score,
        row.status,
        row.observed_created_at,
    )
    retained = (
        review.package_id,
        review.base_candidate_id,
        review.lead_score,
        review.status.value,
        review.created_at.isoformat(),
    )
    if indexed != retained:
        raise ValueError("original workflow review package index and payload disagree")
    if review.package_id != package_id or review.base_candidate_id != candidate_key:
        raise ValueError("original workflow review package source identity disagrees")
    return review
