"""Inspect retained parcel claims for one exact stored CEQA or permit record."""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.operator_dashboard_models import RecordKind
from constructionsight.operator_parcel_models import (
    ParcelCandidateClaim,
    ParcelCandidatePoint,
    ParcelCandidatesSnapshot,
)
from constructionsight.operator_source_candidate import SourceRecordNotFound
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.permit_models import PermitRecord
from constructionsight.site_resolution_service import normalize_apn
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.parcel_site_orm import ParcelCoreRecordRow

PARCEL_CANDIDATE_LIMIT = 20
_GEODETIC_CRS = {
    "EPSG:4326", "CRS84", "OGC:CRS84", "URN:OGC:DEF:CRS:OGC::CRS84",
}
_TARGET_COUNTIES = {"san bernardino", "riverside"}


def _county(value: str) -> str:
    return value.strip().lower().removesuffix(" county")


def inspect_parcel_candidates(
    session: Session, *, kind: RecordKind, record_id: str
) -> ParcelCandidatesSnapshot:
    """Find bounded, source-claimed parcel records for one exact source identity."""

    if kind not in {"ceqa", "permit"} or (
        not record_id or len(record_id) > 255 or record_id != record_id.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in record_id)
    ):
        raise ValueError("invalid exact source record selection")
    record: CeqaRecord | PermitRecord | None = (
        CeqaStore(session).get(record_id) if kind == "ceqa"
        else PermitStore(session).get(record_id)
    )
    if record is None:
        raise SourceRecordNotFound("source record not found")
    site = record.site
    apn = site.apn if site else None
    normalized = normalize_apn(apn) if apn else None
    county = record.county
    result = ParcelCandidatesSnapshot(
        source_kind=kind,
        source_record_id=record_id,
        source_apn=apn,
        normalized_apn=normalized,
        source_county=county,
        matches=[],
        matching_total=0,
        returned=0,
        result_limit=PARCEL_CANDIDATE_LIMIT,
        truncated=False,
    )
    if not site or not apn or not normalized:
        result.limitations.append("The selected source record lacks a usable site APN.")
        return result
    if (
        not county or _county(county) not in _TARGET_COUNTIES
        or site.state.upper() != "CA" or _county(site.county) != _county(county)
    ):
        result.limitations.append(
            "Source site and record county/state are missing, conflicting, or outside scope."
        )
        return result
    # Exact normalized APN + normalized named county; do not join on name or address.
    county_filter = func.lower(func.trim(ParcelCoreRecordRow.county)).in_(
        [_county(county), f"{_county(county)} county"]
    )
    conditions = (
        ParcelCoreRecordRow.normalized_apn == normalized,
        county_filter,
        ParcelCoreRecordRow.state == "CA",
    )
    total = session.scalar(
        select(func.count()).select_from(ParcelCoreRecordRow).where(*conditions)
    ) or 0
    rows = session.scalars(
        select(ParcelCoreRecordRow)
        .where(*conditions).order_by(ParcelCoreRecordRow.id)
        .limit(PARCEL_CANDIDATE_LIMIT)
    ).all()
    result.matching_total = total
    result.truncated = total > len(rows)
    for row in rows:
        try:
            parcel = ParcelCoreRecord.model_validate(json.loads(row.payload_json))
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid retained parcel source payload") from exc
        geometry = parcel.geometry
        indexed = (
            row.parcel_record_id, row.source_key, row.source_record_id,
            row.apn, row.normalized_apn, row.county, row.state,
            row.address, row.geometry_kind, row.geometry_hash,
            row.centroid_latitude, row.centroid_longitude,
            row.spatial_reference, row.source_updated_at,
        )
        payload = (
            parcel.parcel_record_id, parcel.source_key, parcel.source_record_id,
            parcel.apn, parcel.normalized_apn, parcel.county, parcel.state,
            parcel.address, geometry.geometry_kind.value if geometry else None,
            geometry.geometry_hash if geometry else None,
            geometry.centroid_latitude if geometry else None,
            geometry.centroid_longitude if geometry else None,
            geometry.spatial_reference if geometry else None,
            parcel.source_updated_at.isoformat() if parcel.source_updated_at else None,
        )
        if indexed != payload or (
            parcel.normalized_apn != normalized or _county(parcel.county) != _county(county)
            or parcel.state != "CA"
        ):
            raise ValueError("retained parcel source index and payload disagree")
        point = None
        map_reason = "No usable source-claimed geodetic centroid is available."
        if geometry is not None:
            crs = (geometry.spatial_reference or "").strip().upper().replace(" ", "")
            lat, lon = geometry.centroid_latitude, geometry.centroid_longitude
            unsafe_geometry = any(
                "conflict" in note.lower() or "unparsed" in note.lower()
                or "outside" in note.lower() for note in geometry.limitations
            )
            if (
                crs in _GEODETIC_CRS and lat is not None and lon is not None
                and -85.05112878 <= lat <= 85.05112878 and -180 <= lon <= 180
                and not unsafe_geometry
            ):
                point = ParcelCandidatePoint(latitude=lat, longitude=lon)
                map_reason = (
                    "Geodetic parcel centroid claimed by a retained source; "
                    "not an independently verified boundary or site match."
                )
            elif not crs:
                map_reason = "Parcel centroid withheld: geographic CRS is not explicit."
            elif crs not in _GEODETIC_CRS:
                map_reason = "Parcel centroid withheld: unsupported or projected CRS."
        result.matches.append(
            ParcelCandidateClaim(
                parcel_record_id=parcel.parcel_record_id,
                source_key=parcel.source_key,
                source_record_id=parcel.source_record_id,
                apn=parcel.apn,
                county=parcel.county,
                address=parcel.address,
                zoning=parcel.zoning,
                land_use=parcel.land_use,
                source_updated_at=(
                    parcel.source_updated_at.isoformat()
                    if parcel.source_updated_at is not None else None
                ),
                geometry_kind=(geometry.geometry_kind.value if geometry else None),
                spatial_reference=(geometry.spatial_reference if geometry else None),
                point=point,
                map_reason=map_reason,
                limitations=[
                    *parcel.limitations, *(geometry.limitations if geometry else [])
                ],
            )
        )
    result.returned = len(result.matches)
    return result
