"""One reviewed source-backed ArcGIS parcel into the existing investigation worker.

ParcelCoreRecord storage never implies a project. An independent source replay
approval is required before the *same* native investigation job engine sees it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.command_center_arcgis_parcel import (
    _RECORD_KEYS,
    _canonical,
    _retained_record,
)
from constructionsight.command_center_legacy_reconciliation import (
    _native,
    _queue_sources,
)
from constructionsight.intelligence.investigation_sources import from_parcel
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_observation_service import build_parcel_record_observation
from constructionsight.storage.database import (
    create_private_database_engine,
    ensure_database_transaction,
)
from constructionsight.storage.parcel_site_orm import (
    ParcelCoreRecordRow,
    ParcelRecordObservationRow,
)

_PREVIEW_KEYS = _RECORD_KEYS | {"expected_parcel_sha256"}
_QUEUE_KEYS = _PREVIEW_KEYS | {
    "expected_native_evidence_id", "action", "review_reason",
    "caller_confirmation",
}


def _persisted_exact(
    directory: Path, proof: Path | None, payload: dict[str, Any],
) -> tuple[ParcelCoreRecord, dict[str, Any], dict[str, Any]]:
    if type(payload) is not dict or set(payload) != _PREVIEW_KEYS:
        raise ValueError("exact retained parcel proof and reviewed parcel digest required")
    parcel, provenance = _retained_record(
        directory, proof, {key: payload[key] for key in _RECORD_KEYS},
    )
    digest = hashlib.sha256(_canonical(parcel.to_dict())).hexdigest()
    if payload["expected_parcel_sha256"] != digest:
        raise ValueError("retained ArcGIS parcel content changed since review")
    db = directory / "investigations.sqlite3"
    if not db.is_file() or db.is_symlink():
        raise ValueError("separately approved native parcel record does not exist")
    engine = create_private_database_engine(db, create=False)
    try:
        with Session(engine) as session:
            ensure_database_transaction(session)
            matches = session.scalars(select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.source_key == parcel.source_key,
                ParcelCoreRecordRow.source_record_id == parcel.source_record_id,
            )).all()
            if len(matches) != 1 or matches[0].parcel_record_id != parcel.parcel_record_id:
                raise ValueError("original parcel source identity is absent or ambiguous")
            row = matches[0]
            stored = ParcelCoreRecord.model_validate(json.loads(row.payload_json))
            if _canonical(stored.to_dict()) != _canonical(parcel.to_dict()) or (
                row.source_key != parcel.source_key
                or row.source_record_id != parcel.source_record_id
                or row.normalized_apn != parcel.normalized_apn
                or row.county != parcel.county
            ):
                raise ValueError("stored original parcel differs from verified source response")
            observed = build_parcel_record_observation(parcel)
            receipt = session.scalar(select(ParcelRecordObservationRow).where(
                ParcelRecordObservationRow.observation_id == observed.observation_id,
            ))
            if receipt is None or (
                receipt.parcel_record_id != parcel.parcel_record_id
                or receipt.source_key != parcel.source_key
                or receipt.record_digest != observed.record_digest
                or receipt.content_digest != observed.content_digest
                or json.loads(receipt.payload_json) != observed.to_dict()
            ):
                raise ValueError("original parcel observation was not durably verified")
    finally:
        engine.dispose()
    source = from_parcel(parcel)
    raw = parcel.to_dict()
    metadata = {
        "kind": "parcel",
        "record_id": source.evidence.source_record_id,
        "parcel_record_id": parcel.parcel_record_id,
        "source_key": parcel.source_key,
        "source_sha256": hashlib.sha256(_canonical(raw)).hexdigest(),
    }
    return parcel, metadata, provenance


def preview_arcgis_parcel_investigation(
    directory: Path, proof: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Compare exactly approved source-backed parcel to current native worker reality."""
    parcel, metadata, provenance = _persisted_exact(directory, proof, payload)
    state = _native(directory, kind="parcel", raw=parcel.to_dict())
    return {
        "schema_version": "constructionsight.arcgis-parcel-investigation-preview/v1",
        **provenance,
        "parcel_record_id": parcel.parcel_record_id,
        "parcel_sha256": metadata["source_sha256"],
        "original_source": metadata,
        **state,
        "replay_eligible": state["native_state"] == "not_in_native_store",
        "worker_handoff_requires_confirmation": True,
        "unverified_source_claim_only": True,
        "geometry_invented": False,
        "parcel_to_project_identity_verified": False,
        "commercial_authority_granted": False,
        "network_executed": False,
    }


def enqueue_arcgis_parcel_investigation(
    directory: Path, proof: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Enqueue the existing original replay job after a third, distinct review."""
    if type(payload) is not dict or set(payload) != _QUEUE_KEYS:
        raise ValueError("exact independent parcel investigation approval required")
    reason = payload["review_reason"]
    if (
        payload["caller_confirmation"] is not True
        or type(reason) is not str
        or not 10 <= len(reason.strip()) <= 2000
        or payload["action"] not in ("retain_missing", "retain_revision")
    ):
        raise ValueError("affirmative exact worker review and reason required")
    preview = preview_arcgis_parcel_investigation(
        directory, proof, {key: payload[key] for key in _PREVIEW_KEYS},
    )
    if preview["native_evidence_id"] != payload["expected_native_evidence_id"]:
        raise ValueError("current investigation evidence changed since review")
    revision = payload["action"] == "retain_revision"
    if revision and not preview["revision_replay_eligible"]:
        raise ValueError("source revision requires a separately eligible native state")
    if not revision and not preview["replay_eligible"]:
        raise ValueError("parcel already exists in common investigation or conflicts")
    parcel, metadata, _ = _persisted_exact(
        directory, proof, {key: payload[key] for key in _PREVIEW_KEYS},
    )
    response = _queue_sources(
        directory, [(metadata, parcel.to_dict())], reason.strip(),
        previous_evidence_id=(
            preview["native_evidence_id"] if revision else None
        ),
    )
    return {
        **response["jobs"][0],
        "selected_parcel_record_id": parcel.parcel_record_id,
        "original_response_sha256": preview["response_sha256"],
        "native_worker_required": True,
        "unverified_source_claim_only": True,
        "parcel_to_project_identity_verified": False,
        "commercial_authority_granted": False,
    }
