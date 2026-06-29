"""Build parcel core records from previewed rows."""

from __future__ import annotations

import hashlib

from constructionsight.parcel_core_models import ParcelCoreRecord, ParcelGeometryKind
from constructionsight.parcel_geometry import normalize_parcel_geometry
from constructionsight.parcel_row_preview_models import ParcelRowPreview


def build_parcel_core_record_from_preview(
    *,
    source_key: str,
    row_preview: ParcelRowPreview,
    raw_geometry: str | None = None,
    spatial_reference: str | None = None,
) -> ParcelCoreRecord:
    """Build a parcel core record from a usable row preview."""

    if not row_preview.usable:
        raise ValueError("cannot build parcel core record from unusable row preview")
    if row_preview.normalized_apn is None or row_preview.county is None:
        raise ValueError("parcel core record requires normalized APN and county")

    geometry = (
        normalize_parcel_geometry(
            raw_geometry=raw_geometry,
            geometry_kind=ParcelGeometryKind.UNKNOWN,
            spatial_reference=spatial_reference,
        )
        if raw_geometry is not None
        else None
    )
    address = row_preview.normalized_address
    return ParcelCoreRecord(
        parcel_record_id=_parcel_record_id(
            source_key=source_key,
            normalized_apn=row_preview.normalized_apn,
            source_record_id=row_preview.source_record_id,
        ),
        source_key=source_key,
        source_record_id=row_preview.source_record_id,
        apn=row_preview.normalized_apn,
        normalized_apn=row_preview.normalized_apn,
        county=row_preview.county,
        address=address,
        normalized_address=address,
        geometry=geometry,
        limitations=list(row_preview.limitations),
    )


def _parcel_record_id(
    *,
    source_key: str,
    normalized_apn: str,
    source_record_id: str | None,
) -> str:
    """Build a deterministic parcel record id."""

    basis = "|".join([source_key, normalized_apn, source_record_id or ""])
    return f"parcel:{hashlib.sha256(basis.encode('utf-8')).hexdigest()[:16]}"
