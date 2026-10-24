"""Original parcel-to-native evidence replay through the existing audited worker.

Only exact retained ParcelCoreRecord identities are supported. The source remains
read-only; an operator-approved replay is an unverified source observation, never
parcel-to-project confirmation or permission to contact/bid.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.command_center_legacy_reconciliation import (
    _canonical,
    _native,
    _queue_sources,
    _require_separate_original,
)
from constructionsight.intelligence.investigation_sources import from_parcel
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.storage.database import ensure_database_transaction
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.parcel_site_orm import ParcelCoreRecordRow


class ReviewedParcelReplay(BaseModel):
    """One exact user-reviewed source snapshot and its optimistic concurrency state."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    parcel_record_id: str = Field(min_length=1, max_length=255)
    expected_source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_native_evidence_id: str | None = Field(default=None, max_length=255)
    action: Literal["retain_missing", "retain_revision"]
    caller_confirmation: Literal[True]
    review_reason: str = Field(min_length=10, max_length=2000)

    @field_validator("caller_confirmation", mode="before")
    @classmethod
    def exact_confirmation(cls, value: Any) -> Literal[True]:
        if value is not True:
            raise ValueError("explicit boolean confirmation is required")
        return True


def _original_parcel(
    database: Path | None, parcel_record_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if (
        not parcel_record_id.strip()
        or parcel_record_id != parcel_record_id.strip()
        or len(parcel_record_id) > 255
        or any(ord(char) < 32 or ord(char) == 127 for char in parcel_record_id)
    ):
        raise ValueError("one exact original parcel record ID required")
    if database is None:
        raise ValueError("original operator source database is not configured")
    if database.is_symlink() or not database.is_file():
        raise ValueError("original operator database must be an existing regular file")
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            ensure_database_transaction(session)
            row = session.scalar(select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.parcel_record_id == parcel_record_id
            ))
            if row is None:
                raise ValueError("original parcel record not found")
            try:
                parcel = ParcelCoreRecord.model_validate(json.loads(row.payload_json))
            except (ValueError, TypeError) as exc:
                raise ValueError("original parcel payload failed verification") from exc
            geometry = parcel.geometry
            indexed = (
                row.parcel_record_id, row.source_key, row.source_record_id,
                row.apn, row.normalized_apn, row.county, row.state,
                row.address, row.normalized_address, row.jurisdiction,
                row.zoning, row.land_use, row.acreage,
                row.geometry_kind, row.geometry_hash,
                row.centroid_latitude, row.centroid_longitude,
                row.envelope_min_latitude, row.envelope_min_longitude,
                row.envelope_max_latitude, row.envelope_max_longitude,
                row.spatial_reference, row.source_updated_at, row.observed_created_at,
            )
            actual = (
                parcel.parcel_record_id, parcel.source_key, parcel.source_record_id,
                parcel.apn, parcel.normalized_apn, parcel.county, parcel.state,
                parcel.address, parcel.normalized_address, parcel.jurisdiction,
                parcel.zoning, parcel.land_use, parcel.acreage,
                geometry.geometry_kind.value if geometry else None,
                geometry.geometry_hash if geometry else None,
                geometry.centroid_latitude if geometry else None,
                geometry.centroid_longitude if geometry else None,
                geometry.envelope_min_latitude if geometry else None,
                geometry.envelope_min_longitude if geometry else None,
                geometry.envelope_max_latitude if geometry else None,
                geometry.envelope_max_longitude if geometry else None,
                geometry.spatial_reference if geometry else None,
                parcel.source_updated_at.isoformat() if parcel.source_updated_at else None,
                parcel.created_at.isoformat(),
            )
            if indexed != actual:
                raise ValueError("original parcel index and payload disagree")
            raw = parcel.to_dict()
            observation = from_parcel(parcel)
            return {
                "kind": "parcel",
                # A provider's source ID can differ from our parcel_record_id.
                # The existing worker approval checks the true evidence source ID.
                "record_id": observation.evidence.source_record_id,
                "parcel_record_id": parcel_record_id,
                "source_key": parcel.source_key,
                "county": parcel.county,
                "apn": parcel.apn,
                "source_sha256": hashlib.sha256(_canonical(raw)).hexdigest(),
            }, raw
    finally:
        engine.dispose()


def list_retained_original_parcels(
    directory: Path,
    original_database: Path | None,
    *,
    cursor: str | None = None,
) -> dict[str, Any]:
    """List at most twenty verified retained parcel identities, without mutation.

    An exact selected record must still enter the existing reviewed replay
    preview and positive-consent queue. A source row is not a verified project.
    """
    _require_separate_original(directory, original_database)
    if cursor is not None and (
        not cursor or len(cursor) > 255
        or cursor != cursor.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in cursor)
    ):
        raise ValueError("invalid exact retained parcel page cursor")
    if original_database is None:
        return {
            "schema_version": "constructionsight.original-parcel-browse/v1",
            "available": False, "read_only": True, "rows": [],
            "next_cursor": None, "has_more": False,
            "network_executed": False, "identity_independently_verified": False,
            "commercial_authority_granted": False,
        }
    if original_database.is_symlink() or not original_database.is_file():
        raise ValueError("original operator database must be an existing regular file")
    engine = create_operator_read_engine(original_database)
    try:
        with Session(engine, autoflush=False) as session:
            ensure_database_transaction(session)
            query = select(ParcelCoreRecordRow.parcel_record_id)
            if cursor is not None:
                query = query.where(ParcelCoreRecordRow.parcel_record_id > cursor)
            ids = session.scalars(
                query.order_by(ParcelCoreRecordRow.parcel_record_id).limit(21)
            ).all()
    finally:
        engine.dispose()
    visible = ids[:20]
    # Reuse the exact original indexed-payload validation, not a new parser.
    rows = [_original_parcel(original_database, item)[0] for item in visible]
    return {
        "schema_version": "constructionsight.original-parcel-browse/v1",
        "available": True, "read_only": True, "rows": rows,
        "next_cursor": visible[-1] if len(ids) > 20 else None,
        "has_more": len(ids) > 20,
        "page_size": 20,
        "network_executed": False,
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
    }


def preview_original_parcel_reconciliation(
    directory: Path, original_database: Path | None, parcel_record_id: str,
) -> dict[str, Any]:
    """Review exact original parcel provenance and the current canonical worker state."""
    _require_separate_original(directory, original_database)
    metadata, raw = _original_parcel(original_database, parcel_record_id)
    state = _native(directory, kind="parcel", raw=raw)
    return {
        "schema_version": "constructionsight.original-parcel-reconciliation/v1",
        "available": True,
        "read_only": True,
        "original_source": metadata,
        **state,
        "replay_eligible": state["native_state"] == "not_in_native_store",
        "replay_means": "queued_unverified_parcel_observation_only",
        "no_network_collection": True,
        "no_commercial_authorization": True,
        "parcel_to_project_identity_verified": False,
    }


def enqueue_original_parcel_reconciliation(
    directory: Path, original_database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Delegate exact confirmed parcel replay to existing audited original queue."""
    request = ReviewedParcelReplay.model_validate(payload)
    preview = preview_original_parcel_reconciliation(
        directory, original_database, request.parcel_record_id,
    )
    if preview["original_source"]["source_sha256"] != request.expected_source_sha256:
        raise ValueError("original parcel changed; inspect current retained source again")
    if preview["native_evidence_id"] != request.expected_native_evidence_id:
        raise ValueError("canonical parcel evidence changed; inspect again")
    revision = request.action == "retain_revision"
    if revision and not preview["revision_replay_eligible"]:
        raise ValueError("original parcel revision is stale, historical or unchanged")
    if not revision and not preview["replay_eligible"]:
        raise ValueError("parcel already retained or contradictory; review current evidence")
    metadata, raw = _original_parcel(original_database, request.parcel_record_id)
    if metadata["source_sha256"] != request.expected_source_sha256:
        raise ValueError("parcel changed during original source selection")
    result = _queue_sources(
        directory, [(metadata, raw)], request.review_reason,
        previous_evidence_id=preview["native_evidence_id"] if revision else None,
    )
    return {
        **result["jobs"][0],
        "selected_parcel_record_id": request.parcel_record_id,
        "unverified_parcel_claim_only": True,
        "parcel_to_project_identity_verified": False,
    }
