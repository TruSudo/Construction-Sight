"""Tests for the composed operator-dashboard view model."""

from __future__ import annotations

from constructionsight.lead_operator_models import (
    LeadOperatorRecord,
    LeadOperatorRecordKind,
)
from constructionsight.operator_dashboard import _dashboard_lead


def _record(
    kind: LeadOperatorRecordKind,
    record_id: str,
    **values: object,
) -> LeadOperatorRecord:
    return LeadOperatorRecord(
        record_kind=kind,
        record_id=record_id,
        payload=values.pop("payload", {}),
        **values,
    )


def test_dashboard_lead_joins_review_and_enrichment_payloads() -> None:
    workflow = _record(
        LeadOperatorRecordKind.WORKFLOW,
        "workflow-1",
        workflow_id="workflow-1",
        package_id="package-1",
        base_candidate_id="candidate-1",
        status="ready",
        lead_score=81,
        payload={},
    )
    review = _record(
        LeadOperatorRecordKind.REVIEW,
        "package-1",
        base_candidate_id="candidate-1",
        payload={"evidence_notes": ["permit issued"]},
    )
    enrichment = _record(
        LeadOperatorRecordKind.ENRICHMENT,
        "report-1",
        base_candidate_id="candidate-1",
        payload={
            "title": "Ontario Logistics Center",
            "jurisdiction": "San Bernardino County",
            "site": {"latitude": "34.06", "longitude": -117.61},
            "limitations": ["contractor contact not yet verified"],
        },
    )

    lead = _dashboard_lead(workflow, review, enrichment)

    assert lead.title == "Ontario Logistics Center"
    assert lead.jurisdiction == "San Bernardino County"
    assert lead.point is not None
    assert lead.point.latitude == 34.06
    assert lead.point.longitude == -117.61
    assert lead.evidence_notes == ["permit issued"]
    assert lead.limitations == ["contractor contact not yet verified"]


def test_dashboard_lead_does_not_invent_missing_coordinates() -> None:
    workflow = _record(
        LeadOperatorRecordKind.WORKFLOW,
        "workflow-2",
        workflow_id="workflow-2",
        base_candidate_id="candidate-2",
        status="monitor",
        lead_score=35,
        payload={"latitude": "unknown", "longitude": -117.3},
    )

    lead = _dashboard_lead(workflow, None, None)

    assert lead.point is None
    assert lead.title == "candidate-2"
