"""Read-only application view model for the ConstructionSight operator dashboard."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from constructionsight.lead_operator_models import (
    LeadOperatorRecord,
    LeadOperatorRecordKind,
)
from constructionsight.lead_operator_service import list_lead_operator_records


class DashboardPoint(BaseModel):
    """One coordinate suitable for the initial operator map."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class DashboardLead(BaseModel):
    """Joined, read-only representation of one lead workflow."""

    workflow_id: str
    base_candidate_id: str
    package_id: str | None = None
    status: str
    lead_score: int
    title: str
    jurisdiction: str | None = None
    source_url: str | None = None
    point: DashboardPoint | None = None
    evidence_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class DashboardSnapshot(BaseModel):
    """Complete payload consumed by the first local GUI."""

    leads: list[DashboardLead]
    total: int
    mapped: int
    status_counts: dict[str, int]
    crime_overlay_enabled: bool = False
    read_only: bool = True


def build_dashboard_snapshot(session: Session, *, limit: int = 500) -> DashboardSnapshot:
    """Join persisted lead records into one operator-facing snapshot."""

    workflows = list_lead_operator_records(
        session,
        LeadOperatorRecordKind.WORKFLOW,
        limit=limit,
    )
    reviews = list_lead_operator_records(
        session,
        LeadOperatorRecordKind.REVIEW,
        limit=limit,
    )
    enrichments = list_lead_operator_records(
        session,
        LeadOperatorRecordKind.ENRICHMENT,
        limit=limit,
    )
    review_by_candidate = _newest_by_candidate(reviews)
    enrichment_by_candidate = _newest_by_candidate(enrichments)

    leads = [
        _dashboard_lead(
            workflow,
            review_by_candidate.get(workflow.base_candidate_id or ""),
            enrichment_by_candidate.get(workflow.base_candidate_id or ""),
        )
        for workflow in workflows
    ]
    status_counts: dict[str, int] = {}
    for lead in leads:
        status_counts[lead.status] = status_counts.get(lead.status, 0) + 1
    return DashboardSnapshot(
        leads=leads,
        total=len(leads),
        mapped=sum(lead.point is not None for lead in leads),
        status_counts=status_counts,
    )


def _newest_by_candidate(
    records: list[LeadOperatorRecord],
) -> dict[str, LeadOperatorRecord]:
    result: dict[str, LeadOperatorRecord] = {}
    for record in records:
        if record.base_candidate_id:
            result.setdefault(record.base_candidate_id, record)
    return result


def _dashboard_lead(
    workflow: LeadOperatorRecord,
    review: LeadOperatorRecord | None,
    enrichment: LeadOperatorRecord | None,
) -> DashboardLead:
    payloads = [
        workflow.payload,
        review.payload if review else {},
        enrichment.payload if enrichment else {},
    ]
    candidate_id = workflow.base_candidate_id or "unknown-candidate"
    return DashboardLead(
        workflow_id=workflow.workflow_id or workflow.record_id,
        base_candidate_id=candidate_id,
        package_id=workflow.package_id,
        status=workflow.status or "unknown",
        lead_score=workflow.lead_score or 0,
        title=_first_text(payloads, ("title_hint", "title", "project_name"))
        or candidate_id,
        jurisdiction=_first_text(
            payloads,
            ("jurisdiction_hint", "jurisdiction", "county"),
        ),
        source_url=_first_text(payloads, ("source_url",)),
        point=_find_point(payloads),
        evidence_notes=_first_text_list(payloads, "evidence_notes"),
        limitations=_first_text_list(payloads, "limitations"),
    )


def _find_point(payloads: list[dict[str, Any]]) -> DashboardPoint | None:
    for payload in payloads:
        for candidate in _walk_dicts(payload):
            latitude = _number(candidate.get("latitude", candidate.get("lat")))
            longitude = _number(
                candidate.get("longitude", candidate.get("lon", candidate.get("lng")))
            )
            if latitude is None or longitude is None:
                continue
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                return DashboardPoint(latitude=latitude, longitude=longitude)
    return None


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_walk_dicts(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_dicts(child))
    return found


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _first_text(
    payloads: list[dict[str, Any]],
    keys: tuple[str, ...],
) -> str | None:
    for payload in payloads:
        for candidate in _walk_dicts(payload):
            for key in keys:
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _first_text_list(
    payloads: list[dict[str, Any]],
    key: str,
) -> list[str]:
    for payload in payloads:
        value = payload.get(key)
        if isinstance(value, list):
            return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []
