"""Compose the persisted construction-record and lead-workflow read surfaces."""

from __future__ import annotations

import math
from datetime import date
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.lead_operator_models import LeadOperatorRecordKind
from constructionsight.lead_operator_service import (
    get_lead_operator_record,
    load_persisted_lead_workflow,
)
from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.operator_dashboard_models import (
    DashboardPoint,
    DashboardProject,
    DashboardSnapshot,
    EntityNeighborhoodSnapshot,
    FootprintPoint,
    GeographicFootprintSnapshot,
    MilestoneKind,
    RecordKind,
    RecordSelection,
    SourceMilestone,
)
from constructionsight.permit_models import PermitRecord
from constructionsight.site_models import Site
from constructionsight.storage.lead_workflow_orm import LeadWorkflowRecordRow
from constructionsight.storage.operator_read_store import read_project_page


def build_dashboard_snapshot(
    session: Session,
    *,
    kind: RecordSelection = "all",
    query: str = "",
    county: str = "",
    limit: int = 100,
    offset: int = 0,
) -> DashboardSnapshot:
    """Present exact typed source records without generating commercial authority."""

    if kind not in {"all", "ceqa", "permit"}:
        raise ValueError("kind must be all, ceqa or permit")
    if not 1 <= limit <= 500 or offset < 0 or offset > 1_000_000:
        raise ValueError("invalid page bounds")
    if len(query) > 200 or county not in {"", "San Bernardino", "Riverside"}:
        raise ValueError("invalid search or county filter")
    records, total = read_project_page(
        session, kind=kind, query=query.strip(), county=county, limit=limit, offset=offset
    )
    projects = [_project(record) for record in records]
    return DashboardSnapshot(
        selection=kind,
        projects=projects,
        total=total,
        returned=len(projects),
        mapped_on_page=sum(project.point is not None for project in projects),
        offset=offset,
        limit=limit,
        has_more=offset + len(projects) < total,
    )



FOOTPRINT_SCAN_LIMIT = 5_000


def build_geographic_footprint(
    session: Session,
    *,
    kind: RecordSelection = "all",
    query: str = "",
    county: str = "",
) -> GeographicFootprintSnapshot:
    """Map a bounded whole query without presenting a result page as complete coverage."""

    if kind not in {"all", "ceqa", "permit"}:
        raise ValueError("kind must be all, ceqa or permit")
    if len(query) > 200 or county not in {"", "San Bernardino", "Riverside"}:
        raise ValueError("invalid search or county filter")
    records, total = read_project_page(
        session,
        kind=kind,
        query=query.strip(),
        county=county,
        limit=FOOTPRINT_SCAN_LIMIT,
        offset=0,
    )
    projects = [_project(record) for record in records]
    points: list[FootprintPoint] = []
    for ordinal, project in enumerate(projects):
        point = project.point
        if point is None:
            continue
        points.append(
            FootprintPoint(
                ordinal=ordinal,
                record_id=project.record_id,
                record_kind=project.record_kind,
                title=project.title,
                county=project.county,
                point=point,
            )
        )
    return GeographicFootprintSnapshot(
        selection=kind,
        points=points,
        matching_total=total,
        records_scanned=len(projects),
        mapped_in_scan=len(points),
        scan_limit=FOOTPRINT_SCAN_LIMIT,
        truncated=total > len(projects),
    )


ENTITY_SCAN_LIMIT = 5_000
ENTITY_RESULT_LIMIT = 100


def build_entity_neighborhood(
    session: Session,
    *,
    entity_key: str,
    kind: RecordSelection = "all",
    county: str = "",
) -> EntityNeighborhoodSnapshot:
    """Inspect exact persisted key co-occurrence; do not infer real-world identity."""

    if not entity_key or entity_key != entity_key.strip() or len(entity_key) > 255:
        raise ValueError("invalid entity key")
    if kind not in {"all", "ceqa", "permit"}:
        raise ValueError("kind must be all, ceqa or permit")
    if county not in {"", "San Bernardino", "Riverside"}:
        raise ValueError("invalid county filter")
    records, total = read_project_page(
        session,
        kind=kind,
        query="",
        county=county,
        limit=ENTITY_SCAN_LIMIT,
        offset=0,
    )
    matches: list[DashboardProject] = []
    matching_records_in_scan = 0
    for record in records:
        if not any(entity.entity_key == entity_key for entity in record.entities):
            continue
        matching_records_in_scan += 1
        if len(matches) < ENTITY_RESULT_LIMIT:
            matches.append(_project(record))
    return EntityNeighborhoodSnapshot(
        entity_key=entity_key,
        selection=kind,
        county_filter=county,
        records=matches,
        scanned_source_records=len(records),
        total_source_records=total,
        matching_records_in_scan=matching_records_in_scan,
        returned=len(matches),
        scan_limit=ENTITY_SCAN_LIMIT,
        result_limit=ENTITY_RESULT_LIMIT,
        source_scan_truncated=total > len(records),
        matching_records_truncated=matching_records_in_scan > len(matches),
    )


def _site_point(site: Site | None) -> tuple[DashboardPoint | None, str]:
    if site is None:
        return None, "No site is linked to this source record."
    lat, lon = site.latitude, site.longitude
    if lat is None or lon is None:
        return None, "The linked site has no complete geographic coordinate pair."
    if not math.isfinite(lat) or not math.isfinite(lon):
        return None, "The linked site's coordinates are non-finite."
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        return None, "The linked site's coordinates are outside geographic ranges."
    if abs(lat) > 85.05112878:
        return None, "The coordinate lies outside this Web Mercator map's latitude range."
    if not site.provenance:
        return None, "Coordinates withheld because the linked site has no source provenance."
    return DashboardPoint(
        latitude=lat, longitude=lon, site_key=site.site_key, provenance=site.provenance
    ), "Source-claimed site coordinates; not independently verified."


def _source_milestones(
    record: CeqaRecord | PermitRecord,
) -> tuple[list[SourceMilestone], bool]:
    """Retain available dates and flag contradictions in source-event ordering."""

    observations: list[tuple[MilestoneKind, date | None]]
    if isinstance(record, CeqaRecord):
        observations = [
            ("ceqa_received", record.received_date),
            ("ceqa_posted", record.posted_date),
        ]
        inconsistent = (
            record.received_date is not None
            and record.posted_date is not None
            and record.posted_date < record.received_date
        )
    else:
        observations = [
            ("permit_applied", record.applied_date),
            ("permit_issued", record.issued_date),
            ("permit_finaled", record.finaled_date),
        ]
        dated = [value for _, value in observations if value is not None]
        inconsistent = dated != sorted(dated)
    milestones: list[SourceMilestone] = []
    for event_kind, recorded_date in observations:
        if recorded_date is not None:
            milestones.append(
                SourceMilestone(event_kind=event_kind, recorded_date=recorded_date)
            )
    milestones.sort(key=lambda item: item.recorded_date)
    return milestones, inconsistent


def _project(record: CeqaRecord | PermitRecord) -> DashboardProject:
    site = record.site
    point, reason = _site_point(site)
    milestones, inconsistent_dates = _source_milestones(record)
    county = record.county
    normalized_county = (county or "").strip().lower().removesuffix(" county")
    coverage: Literal["unknown", "target_county", "outside_target_counties"] = (
        "unknown"
        if not county
        else "target_county"
        if normalized_county in {"san bernardino", "riverside"}
        and (site is None or site.state.upper() == "CA")
        else "outside_target_counties"
    )
    limitations = [
        "Source record only; not a qualified lead or verified current construction phase."
    ]
    if not record.provenance:
        limitations.append("Record provenance is missing.")
    if inconsistent_dates:
        limitations.append(
            "Stored milestone dates conflict with source event order; "
            "no construction phase conclusion is supported."
        )
    if point is None:
        limitations.append(reason)
    if coverage == "outside_target_counties":
        limitations.append("The record is outside the stated two-county scope.")
    if site and county and site.county.strip().lower().removesuffix(" county") != normalized_county:
        limitations.append("Record and site counties disagree; location requires review.")
        point = None
        reason = "Coordinates withheld because record and site counties disagree."
        limitations.append(reason)
    if any(not entity.provenance for entity in record.entities):
        limitations.append("Some named parties lack their own provenance; roles are unverified.")
    if isinstance(record, CeqaRecord):
        record_id = record.ceqa_key
        kind: RecordKind = "ceqa"
        title = record.title
        jurisdiction = record.lead_agency
        source_status = record.document_type
        source_number = record.state_clearinghouse_number
    else:
        record_id = record.permit_key
        kind = "permit"
        title = f"Permit {record.permit_number}"
        jurisdiction = record.jurisdiction
        source_status = record.status
        source_number = record.permit_number
    return DashboardProject(
        record_id=record_id,
        record_kind=kind,
        title=title,
        county=county,
        jurisdiction=jurisdiction,
        source_status=source_status,
        source_record_number=source_number,
        milestones=milestones,
        description=record.description,
        site_key=site.site_key if site else None,
        address=site.address if site else None,
        apn=site.apn if site else None,
        point=point,
        map_reason=reason,
        coverage=coverage,
        entities=record.entities,
        provenance=record.provenance,
        limitations=limitations,
    )


def build_workflow_snapshot(
    session: Session, *, limit: int = 100, offset: int = 0
) -> dict[str, Any]:
    """Join the workflow's exact package ID, never the newest unrelated candidate review."""

    if not 1 <= limit <= 500 or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid page bounds")
    workflow_ids = session.scalars(
        select(LeadWorkflowRecordRow.workflow_id)
        .order_by(LeadWorkflowRecordRow.id)
        .offset(offset)
        .limit(limit)
    ).all()
    leads: list[dict[str, Any]] = []
    for workflow_id in workflow_ids:
        workflow = load_persisted_lead_workflow(session, workflow_id)
        review_row = get_lead_operator_record(
            session, LeadOperatorRecordKind.REVIEW, workflow.package_id
        )
        notes: list[str] = []
        summary = None
        limitations = list(workflow.limitations)
        if review_row is None:
            limitations.append("The workflow's exact review package is missing.")
        else:
            review = LeadReviewPackage.model_validate(review_row.payload)
            if (
                review.package_id != workflow.package_id
                or review.base_candidate_id != workflow.base_candidate_id
            ):
                raise ValueError("workflow and review package identity disagree")
            notes = list(review.evidence_notes)
            summary = review.summary
            limitations.extend(review.limitations)
        leads.append(
            {
                **workflow.to_dict(),
                "summary": summary,
                "evidence_notes": notes,
                "limitations": list(dict.fromkeys(limitations)),
            }
        )
    total = session.scalar(select(func.count()).select_from(LeadWorkflowRecordRow)) or 0
    return {
        "leads": leads,
        "total": total,
        "returned": len(leads),
        "has_more": offset + len(leads) < total,
        "offset": offset,
        "limit": limit,
        "read_only": True,
    }
