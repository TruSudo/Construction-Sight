"""Store helpers for parcel core and site-resolution records."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.site_resolution_models import SiteResolutionResult
from constructionsight.storage.parcel_site_orm import (
    ParcelCoreRecordRow,
    SiteResolutionResultRow,
)


def store_parcel_core_record(
    session: Session,
    parcel: ParcelCoreRecord,
) -> ParcelCoreRecordRow:
    """Insert or update a parcel core record."""

    session.flush()
    payload_json = _payload_json(parcel.to_dict())
    existing = session.execute(
        select(ParcelCoreRecordRow).where(
            ParcelCoreRecordRow.parcel_record_id == parcel.parcel_record_id
        )
    ).scalar_one_or_none()
    geometry = parcel.geometry
    if existing is None:
        existing = ParcelCoreRecordRow(
            parcel_record_id=parcel.parcel_record_id,
            source_key=parcel.source_key,
            source_record_id=parcel.source_record_id,
            apn=parcel.apn,
            normalized_apn=parcel.normalized_apn,
            county=parcel.county,
            state=parcel.state,
            address=parcel.address,
            normalized_address=parcel.normalized_address,
            jurisdiction=parcel.jurisdiction,
            zoning=parcel.zoning,
            land_use=parcel.land_use,
            acreage=parcel.acreage,
            geometry_kind=geometry.geometry_kind.value if geometry else None,
            geometry_hash=geometry.geometry_hash if geometry else None,
            centroid_latitude=geometry.centroid_latitude if geometry else None,
            centroid_longitude=geometry.centroid_longitude if geometry else None,
            envelope_min_latitude=geometry.envelope_min_latitude if geometry else None,
            envelope_min_longitude=geometry.envelope_min_longitude if geometry else None,
            envelope_max_latitude=geometry.envelope_max_latitude if geometry else None,
            envelope_max_longitude=geometry.envelope_max_longitude if geometry else None,
            spatial_reference=geometry.spatial_reference if geometry else None,
            source_updated_at=(
                parcel.source_updated_at.isoformat() if parcel.source_updated_at else None
            ),
            observed_created_at=parcel.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.source_key = parcel.source_key
    existing.source_record_id = parcel.source_record_id
    existing.apn = parcel.apn
    existing.normalized_apn = parcel.normalized_apn
    existing.county = parcel.county
    existing.state = parcel.state
    existing.address = parcel.address
    existing.normalized_address = parcel.normalized_address
    existing.jurisdiction = parcel.jurisdiction
    existing.zoning = parcel.zoning
    existing.land_use = parcel.land_use
    existing.acreage = parcel.acreage
    existing.geometry_kind = geometry.geometry_kind.value if geometry else None
    existing.geometry_hash = geometry.geometry_hash if geometry else None
    existing.centroid_latitude = geometry.centroid_latitude if geometry else None
    existing.centroid_longitude = geometry.centroid_longitude if geometry else None
    existing.envelope_min_latitude = geometry.envelope_min_latitude if geometry else None
    existing.envelope_min_longitude = geometry.envelope_min_longitude if geometry else None
    existing.envelope_max_latitude = geometry.envelope_max_latitude if geometry else None
    existing.envelope_max_longitude = geometry.envelope_max_longitude if geometry else None
    existing.spatial_reference = geometry.spatial_reference if geometry else None
    existing.source_updated_at = (
        parcel.source_updated_at.isoformat() if parcel.source_updated_at else None
    )
    existing.observed_created_at = parcel.created_at.isoformat()
    existing.payload_json = payload_json
    return existing


def store_site_resolution_result(
    session: Session,
    result: SiteResolutionResult,
) -> SiteResolutionResultRow:
    """Insert or update a source-neutral site-resolution result."""

    session.flush()
    payload_json = _payload_json(result.to_dict())
    existing = session.execute(
        select(SiteResolutionResultRow).where(
            SiteResolutionResultRow.resolution_id == result.resolution_id
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = SiteResolutionResultRow(
            resolution_id=result.resolution_id,
            source_name=result.source_name,
            evidence_id=result.evidence_id,
            status=result.status.value,
            primary_site_key=result.primary_site_key,
            candidate_count=len(result.candidates),
            conflict_count=len(result.conflicts),
            limitation_count=len(result.limitations),
            observed_created_at=result.created_at.isoformat(),
            payload_json=payload_json,
        )
        session.add(existing)
        return existing
    existing.source_name = result.source_name
    existing.evidence_id = result.evidence_id
    existing.status = result.status.value
    existing.primary_site_key = result.primary_site_key
    existing.candidate_count = len(result.candidates)
    existing.conflict_count = len(result.conflicts)
    existing.limitation_count = len(result.limitations)
    existing.observed_created_at = result.created_at.isoformat()
    existing.payload_json = payload_json
    return existing


def _payload_json(payload: dict[str, object]) -> str:
    """Return deterministic JSON payload."""

    return json.dumps(payload, sort_keys=True)
