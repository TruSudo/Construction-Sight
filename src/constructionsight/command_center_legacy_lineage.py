"""Read-only original workflow lineage against one exact native source identity.

A matching original candidate key is provenance of that specific historical
source candidate only. It does not verify same-project identity, migrate money,
authorize a sales action or change the canonical investigation state.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.command_center_legacy_reconciliation import (
    preview_legacy_reconciliation,
)
from constructionsight.lead_operator_models import LeadOperatorRecordKind
from constructionsight.lead_operator_service import (
    get_lead_operator_record,
    load_persisted_lead_workflow,
)
from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.storage.lead_workflow_orm import (
    LeadWorkflowRecordRow,
    ResultLedgerRecordRow,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine


def original_candidate_workflow_lineage(
    directory: Path,
    operator_database: Path | None,
    *,
    kind: Literal["ceqa", "permit"],
    record_id: str,
    offset: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """Inspect exact original candidate-derived workflow records without a join guess."""

    if type(offset) is not int or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid original workflow lineage page offset")
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("invalid original workflow lineage page limit")
    source = preview_legacy_reconciliation(
        directory, operator_database, kind=kind, record_id=record_id
    )
    candidate_key: str = source["original_source"]["candidate_key"]
    assert operator_database is not None
    engine = create_operator_read_engine(operator_database)
    try:
        with Session(engine, autoflush=False) as session:
            predicate = LeadWorkflowRecordRow.base_candidate_id == candidate_key
            total = session.scalar(
                select(func.count()).select_from(LeadWorkflowRecordRow).where(predicate)
            ) or 0
            workflow_ids = session.scalars(
                select(LeadWorkflowRecordRow.workflow_id)
                .where(predicate)
                .order_by(LeadWorkflowRecordRow.id)
                .offset(offset)
                .limit(limit)
            ).all()
            rows: list[dict[str, Any]] = []
            for workflow_id in workflow_ids:
                workflow = load_persisted_lead_workflow(session, workflow_id)
                if workflow.base_candidate_id != candidate_key:
                    raise ValueError("indexed original candidate/workflow lineage disagrees")
                review_record = get_lead_operator_record(
                    session, LeadOperatorRecordKind.REVIEW, workflow.package_id
                )
                review_status = "missing_review_package"
                if review_record is not None:
                    review = LeadReviewPackage.model_validate(review_record.payload)
                    if (
                        review.package_id != workflow.package_id
                        or review.base_candidate_id != candidate_key
                    ):
                        raise ValueError("original workflow review package identity disagrees")
                    review_status = review.status.value
                result_count = session.scalar(
                    select(func.count()).select_from(ResultLedgerRecordRow).where(
                        ResultLedgerRecordRow.workflow_id == workflow.workflow_id
                    )
                ) or 0
                rows.append({
                    "workflow_id": workflow.workflow_id,
                    "original_package_id": workflow.package_id,
                    "original_candidate_key": candidate_key,
                    "historical_workflow_status": workflow.status.value,
                    "review_package_status": review_status,
                    "original_result_revision_count_unverified": result_count,
                    "original_workflow_limitations": list(workflow.limitations),
                    "canonical_investigation_id": (
                        source["canonical_investigation_id"]
                        if source["native_state"] == "exact_observation_already_retained"
                        else None
                    ),
                    "lineage_basis": "exact_original_source_candidate_key",
                    "identity_association_verified": False,
                    "commercial_authority_granted": False,
                    "result_share_or_payment_verified": False,
                })
    finally:
        engine.dispose()
    return {
        "schema_version": "constructionsight.original-workflow-candidate-lineage/v1",
        "original_source": source["original_source"],
        "source_entity_id": source["source_entity_id"],
        "native_state": source["native_state"],
        "canonical_investigation_id": source["canonical_investigation_id"],
        "lineage_basis": "exact_original_source_candidate_key",
        "matching_workflow_total": total,
        "matching_workflows": rows,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "read_only": True,
        "identity_association_verified": False,
        "commercial_authority_granted": False,
        "result_share_or_payment_verified": False,
        "limitations": [
            "Candidate lineage does not prove reviewed identity between distinct projects.",
            "Historical workflow status does not grant new outreach or bidding authority.",
            "Result revision counts are not validation of outcome, royalty or payment.",
            "Unmatched original workflows cannot be linked without independent evidence.",
        ],
    }
