"""Review exact retained ArcGIS bytes before inserting an original parcel record.

The checked original source stays immutable; only the existing native private
database can accept a separately authorized parcel observation. This is not a
parcel-to-site match or a lead qualification.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.command_center_arcgis_proofs import (
    preview_arcgis_proof_record_request,
)
from constructionsight.command_center_arcgis_record import _verify_exact_arcgis_feature
from constructionsight.local_operator_authorization import (
    authorize_local_operator_operation,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_observation_service import build_parcel_record_observation
from constructionsight.parcel_record_builder import build_parcel_core_record_from_preview
from constructionsight.parcel_row_preview_models import ParcelRowPreview
from constructionsight.storage.database import ensure_database_transaction
from constructionsight.storage.parcel_site_orm import ParcelCoreRecordRow
from constructionsight.storage.parcel_site_store import (
    store_parcel_core_record,
    store_parcel_record_observation,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text

_RECORD_KEYS = {
    "source_key", "expected_bundle_id", "expected_bundle_sha256",
    "expected_snapshot_id", "object_id", "expected_plan_id",
    "expected_response_sha256",
}
_APPLY_KEYS = _RECORD_KEYS | {
    "expected_parcel_sha256", "expected_native_state", "review_reason",
    "caller_confirmation",
}
_RECORD_EVIDENCE_KEYS = {
    "schema_version", "plan_id", "source_key", "bundle_id", "bundle_sha256",
    "snapshot_id", "object_id", "request_url", "response_sha256",
    "response_body_base64", "observed_at", "report", "network_executed",
    "parcel_persisted", "site_identity_verified", "commercial_authority_granted",
}


def _canonical(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _retained_record(
    directory: Path, proof: Path | None, request: dict[str, Any],
) -> tuple[ParcelCoreRecord, dict[str, Any]]:
    if not isinstance(request, dict) or set(request) != _RECORD_KEYS:
        raise ValueError("exact ArcGIS record and original response digest required")
    plan = preview_arcgis_proof_record_request(
        proof, {key: request[key] for key in _RECORD_KEYS if key.startswith(
            "expected_bundle") or key in {
                "source_key", "expected_snapshot_id", "object_id",
            }
        },
    )
    if request["expected_plan_id"] != plan["plan_id"]:
        raise ValueError("ArcGIS record plan changed after source acquisition")
    sha = request["expected_response_sha256"]
    if type(sha) is not str or len(sha) != 64 or any(
        char not in "0123456789abcdef" for char in sha
    ):
        raise ValueError("exact 64-digit original response SHA-256 required")
    evidence_file = plan["plan_id"].replace(":", "-") + ".json"
    evidence_path = directory / "arcgis-record-evidence" / evidence_file
    envelope = json.loads(read_runtime_text(evidence_path, max_bytes=2_000_000))
    if not isinstance(envelope, dict) or set(envelope) != _RECORD_EVIDENCE_KEYS:
        raise ValueError("retained ArcGIS response envelope shape is not authentic")
    expected = {
        "schema_version": "constructionsight.arcgis-single-record-body/v1",
        "plan_id": plan["plan_id"], "source_key": plan["source_key"],
        "bundle_id": plan["bundle_id"],
        "bundle_sha256": plan["bundle_sha256"],
        "snapshot_id": plan["snapshot_id"], "object_id": plan["object_id"],
    }
    if any(envelope[key] != value for key, value in expected.items()) or (
        envelope["network_executed"] is not True
        or envelope["parcel_persisted"] is not False
        or envelope["site_identity_verified"] is not False
        or envelope["commercial_authority_granted"] is not False
    ):
        raise ValueError("original recorded ArcGIS scope or authority was modified")
    from constructionsight.parcel_source_acquisition_http import _exact_request_url

    if envelope["request_url"] != _exact_request_url(
        plan["query_url"], plan["parameters"],
    ):
        raise ValueError("source response request URL differs from reviewed plan")
    try:
        raw = base64.b64decode(envelope["response_body_base64"], validate=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid retained ArcGIS response byte encoding") from exc
    if hashlib.sha256(raw).hexdigest() != sha or envelope["response_sha256"] != sha:
        raise ValueError("retained ArcGIS source response changed after acquisition")
    report = _verify_exact_arcgis_feature(proof, plan, raw)
    if not isinstance(envelope["report"], dict) or (
        envelope["report"]["rows"] != report["rows"]
        or envelope["report"]["source_key"] != report["source_key"]
        or envelope["report"]["usable_row_count"] != 1
    ):
        raise ValueError("retained parcel parser result disagrees with source bytes")
    row = ParcelRowPreview.model_validate(report["rows"][0])
    if row.source_record_id != str(plan["object_id"]):
        raise ValueError("parcel record source identity disagrees with official object ID")
    created = datetime.fromisoformat(envelope["observed_at"])
    if created.tzinfo is None or created.utcoffset() is None:
        raise ValueError("retained source observation time must be timezone-aware")
    initial = build_parcel_core_record_from_preview(
        source_key=plan["source_key"], row_preview=row,
    )
    parcel = ParcelCoreRecord.model_validate({
        **initial.to_dict(),
        "created_at": created.isoformat(),
        "limitations": sorted(set(initial.limitations) | {
            "retained_arcgis_response_sha256:" + sha,
            "retained_arcgis_bundle_sha256:" + plan["bundle_sha256"],
            "source_attributes_only_no_geometry",
            "source_claim_not_independent_project_identity",
        }),
    })
    return parcel, {
        "plan_id": plan["plan_id"],
        "response_sha256": sha,
        "evidence_file": evidence_file,
    }


def _native_state(directory: Path, parcel: ParcelCoreRecord) -> str:
    """Conservatively deny same source identity under a contradictory APN."""
    path = directory / "investigations.sqlite3"
    if path.is_symlink():
        raise ValueError("native parcel database cannot be a symlink")
    if not path.exists():
        return "absent"
    from constructionsight.storage.database import create_private_database_engine

    engine = create_private_database_engine(path, create=False)
    try:
        with Session(engine) as session:
            ensure_database_transaction(session)
            existing = session.scalars(select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.source_key == parcel.source_key,
                ParcelCoreRecordRow.source_record_id == parcel.source_record_id,
            )).all()
            if any(row.parcel_record_id != parcel.parcel_record_id for row in existing):
                return "conflicting_source_identity"
            current = session.scalar(select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.parcel_record_id == parcel.parcel_record_id,
            ))
            if current is None:
                return "absent"
            return (
                "exact_replay" if _canonical(json.loads(current.payload_json))
                == _canonical(parcel.to_dict()) else "conflicting_record_revision"
            )
    finally:
        engine.dispose()


def preview_reviewed_arcgis_parcel(
    directory: Path, proof: Path | None, request: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct one source-evidenced parcel in memory; never modify storage."""
    parcel, provenance = _retained_record(directory, proof, request)
    native = _native_state(directory, parcel)
    return {
        "schema_version": "constructionsight.arcgis-reviewed-parcel-preview/v1",
        **provenance,
        "parcel_record_id": parcel.parcel_record_id,
        "parcel_sha256": hashlib.sha256(_canonical(parcel.to_dict())).hexdigest(),
        "parcel": parcel.to_dict(),
        "native_state": native,
        "may_request_persistence": native in {"absent", "exact_replay"},
        "original_source_bytes_unchanged": True,
        "network_executed": False,
        "parcel_persisted": False,
        "site_identity_verified": False,
        "geometry_verified": False,
        "commercial_authority_granted": False,
    }


def apply_reviewed_arcgis_parcel(
    directory: Path, proof: Path | None, request: dict[str, Any],
) -> dict[str, Any]:
    """Require distinct positive approval for immutable original parcel persistence."""
    if not isinstance(request, dict) or set(request) != _APPLY_KEYS:
        raise ValueError("exact parcel preview and separate authorization required")
    reason = request["review_reason"]
    if (
        request["caller_confirmation"] is not True or type(reason) is not str
        or not 10 <= len(reason.strip()) <= 2_000
    ):
        raise ValueError("explicit parcel persistence confirmation is required")
    preview = preview_reviewed_arcgis_parcel(
        directory, proof, {key: request[key] for key in _RECORD_KEYS},
    )
    if (
        not preview["may_request_persistence"]
        or request["expected_parcel_sha256"] != preview["parcel_sha256"]
        or request["expected_native_state"] != preview["native_state"]
    ):
        raise ValueError("parcel changed, conflicts, or review is stale")
    parcel = ParcelCoreRecord.model_validate(preview["parcel"])
    authorize_local_operator_operation(
        action="persist-reviewed-arcgis-parcel",
        resource_type="original-evidenced-parcel-core-record",
        resource_id=parcel.parcel_record_id,
        exact_scope=(
            "plan-id:" + preview["plan_id"],
            "response-sha256:" + preview["response_sha256"],
            "parcel-sha256:" + preview["parcel_sha256"],
            "native-state:" + preview["native_state"],
        ),
        current_state_identity=preview["parcel_sha256"],
        expected_identity=preview["parcel_sha256"],
        granted_authority=("one verified source-backed parcel record observation",),
        denied_authority=(
            "replace conflicting parcel identity", "geometry invention",
            "automatic project/site merge", "lead qualification",
            "contact outreach or bidding",
        ),
        limitations=(
            "source attributes verify a source claim only",
            "no independent project identity or mapped geometry is asserted",
        ),
        reason=reason.strip(), caller_confirmation=True,
    )
    from constructionsight.investigation_runtime import InvestigationRuntime

    runtime = InvestigationRuntime(directory)
    try:
        with Session(runtime.engine) as session, session.begin():
            ensure_database_transaction(session)
            source_rows = session.scalars(select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.source_key == parcel.source_key,
                ParcelCoreRecordRow.source_record_id == parcel.source_record_id,
            )).all()
            if any(row.parcel_record_id != parcel.parcel_record_id for row in source_rows):
                raise ValueError("source identity conflicts during parcel persistence")
            existing = session.scalar(select(ParcelCoreRecordRow).where(
                ParcelCoreRecordRow.parcel_record_id == parcel.parcel_record_id,
            ))
            if existing is not None and _canonical(json.loads(
                existing.payload_json,
            )) != _canonical(parcel.to_dict()):
                raise ValueError("existing original parcel record cannot be rewritten")
            if request["expected_native_state"] == "absent" and existing is not None:
                raise ValueError("parcel appeared since review; inspect again")
            if request["expected_native_state"] == "exact_replay" and existing is None:
                raise ValueError("parcel disappeared since review; inspect again")
            store_parcel_core_record(session, parcel)
            store_parcel_record_observation(
                session, build_parcel_record_observation(parcel),
            )
    finally:
        runtime.close()
    return {
        "schema_version": "constructionsight.arcgis-reviewed-parcel-persistence/v1",
        "parcel_record_id": parcel.parcel_record_id,
        "source_key": parcel.source_key,
        "source_record_id": parcel.source_record_id,
        "response_sha256": preview["response_sha256"],
        "parcel_sha256": preview["parcel_sha256"],
        "original_source_evidence_retained": True,
        "parcel_persisted": True,
        "observation_retained": True,
        "native_worker_enqueued": False,
        "site_identity_verified": False,
        "geometry_verified": False,
        "commercial_authority_granted": False,
    }
