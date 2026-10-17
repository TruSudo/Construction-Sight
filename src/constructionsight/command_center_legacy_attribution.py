"""Explicit reverse navigation from a preserved workflow to one exact source.

The operator supplies an existing source family and key. The service verifies
its deterministic original candidate identity against the persisted workflow,
then reports only the current native source evidence and historical outcomes.
No name/address/parcel fuzzy join and no commercial action are permitted.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from constructionsight.command_center_legacy_events import verified_original_workflow_events
from constructionsight.command_center_legacy_lineage import _outcome_revision
from constructionsight.command_center_legacy_reconciliation import (
    preview_legacy_reconciliation,
)
from constructionsight.lead_operator_models import LeadOperatorRecordKind
from constructionsight.lead_operator_service import (
    LeadOperatorError,
    get_lead_operator_record,
    load_persisted_lead_workflow,
)
from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.operator_results import read_validated_result_history
from constructionsight.storage.operator_read_store import create_operator_read_engine


def original_workflow_source_attribution(
    directory: Path,
    operator_database: Path | None,
    *,
    workflow_id: str,
    kind: Literal["ceqa", "permit"],
    record_id: str,
) -> dict[str, Any]:
    """Prove an exact original source-to-workflow link without guessing identity."""

    if (
        not workflow_id or len(workflow_id) > 255 or workflow_id.strip() != workflow_id
        or any(ord(c) < 32 or ord(c) == 127 for c in workflow_id)
    ):
        raise ValueError("invalid exact original workflow identity")
    if operator_database is None:
        raise ValueError("original operator source database is not configured")
    # Only exact original records can provide an original candidate key;
    # current native evidence is checked independently in the same preview.
    source = preview_legacy_reconciliation(
        directory, operator_database, kind=kind, record_id=record_id
    )
    candidate_key: str = source["original_source"]["candidate_key"]
    engine = create_operator_read_engine(operator_database)
    try:
        with Session(engine, autoflush=False) as session:
            try:
                workflow = load_persisted_lead_workflow(session, workflow_id)
            except LeadOperatorError as exc:
                raise ValueError("original workflow is missing or inconsistent") from exc
            if workflow.base_candidate_id != candidate_key:
                raise ValueError(
                    "original workflow is not bound to this exact source candidate"
                )
            review_record = get_lead_operator_record(
                session, LeadOperatorRecordKind.REVIEW, workflow.package_id
            )
            if review_record is None:
                raise ValueError("exact original workflow review evidence is missing")
            review = LeadReviewPackage.model_validate(review_record.payload)
            if (
                review.package_id != workflow.package_id
                or review.base_candidate_id != candidate_key
            ):
                raise ValueError("original review package disagrees with exact source identity")
            transition_history = verified_original_workflow_events(session, workflow)
            validated = read_validated_result_history(session, workflow_id)
            if validated is not None and validated["package_id"] != workflow.package_id:
                raise ValueError("original outcome package disagrees with exact workflow")
            history = (
                [_outcome_revision(record) for record in validated["history"]]
                if validated is not None else []
            )
    finally:
        engine.dispose()

    native_exact = source["native_state"] == "exact_observation_already_retained"
    return {
        "schema_version": "constructionsight.original-workflow-source-attribution/v1",
        "read_only": True,
        "original_workflow_id": workflow.workflow_id,
        "original_package_id": workflow.package_id,
        "historical_workflow_status": workflow.status.value,
        "historical_workflow_transition_history": transition_history,
        "review_package_status": review.status.value,
        "original_source": source["original_source"],
        "source_entity_id": source["source_entity_id"],
        "expected_evidence_id": source["expected_evidence_id"],
        "native_evidence_id": source["native_evidence_id"],
        "native_state": source["native_state"],
        "canonical_investigation_id": (
            source["canonical_investigation_id"] if native_exact else None
        ),
        "attribution_basis": "exact_original_source_candidate_key",
        "historical_result": {
            "has_retained_outcome": validated is not None,
            "history_integrity_validated": validated is not None,
            "revision_count": len(history),
            "current_revision": history[-1] if history else None,
            "revision_history": history,
            "latest_revision_only_is_current": True,
            "past_revisions_must_not_be_summed": True,
        },
        "source_identity_match": True,
        "current_native_observation_matches_original": native_exact,
        "same_project_identity_independently_verified": False,
        "contract_verified": False,
        "royalty_entitlement_verified": False,
        "payment_received_verified": False,
        "outreach_authorized": False,
        "bid_authorized": False,
        "limitations": [
            "Exact source-candidate equality does not independently verify project identity.",
            "The original workflow status does not authorize fresh commercial activity.",
            "A calculated historical share is not evidence of entitlement or payment.",
            "A missing or disagreeing native observation is not an identity match.",
        ],
    }
