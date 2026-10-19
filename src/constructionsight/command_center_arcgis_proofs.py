"""Native, offline handoff of one original bounded ArcGIS proof to the shared store.

The original proof verifier and scope-bound persistence service own the decision.
This does not acquire GIS data, create a parcel, resolve a project, or authorize commerce.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.command_center_sources import source_inspection
from constructionsight.operator_services.parcel_arcgis_service import (
    ParcelArcGISOperatorServiceError,
    persist_authorized_arcgis_bundle,
)
from constructionsight.parcel_source_acquisition_bundle import (
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_bundle_models import (
    ParcelArcGISBoundedProofBundle,
)
from constructionsight.storage.database import (
    database_url_from_path,
    prepare_private_database,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.parcel_source_acquisition_bundle_store import (
    load_arcgis_bounded_proof_bundles,
)
from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_MAX_PROOF_BYTES = 64 * 1024 * 1024


def _selected_proof(
    path: Path | None,
) -> tuple[str, ParcelArcGISBoundedProofBundle, dict[str, Any]] | None:
    if path is None:
        return None
    # One anchored no-follow read binds the displayed SHA to the parsed proof.
    raw = read_runtime_artifact(path, max_bytes=_MAX_PROOF_BYTES)
    try:
        bundle = ParcelArcGISBoundedProofBundle.model_validate_json(raw)
        verification = verify_arcgis_bounded_proof_bundle(bundle)
    except (ValidationError, ValueError) as exc:
        raise ValueError("configured ArcGIS proof failed original offline verification") from exc
    if not verification.valid:
        raise ValueError("configured ArcGIS proof did not independently verify")
    return hashlib.sha256(raw).hexdigest(), bundle, verification.to_dict()


def retained_arcgis_proof_preview(path: Path | None) -> dict[str, Any]:
    """Inspect a configured local proof without starting collection or writing data."""
    selected = _selected_proof(path)
    if selected is None:
        return {
            "schema_version": "constructionsight.native-arcgis-proof-review/v1",
            "configured": False,
            "available": False,
            "network_executed": False,
            "source_database_mutated": False,
            "parcel_imported": False,
            "commercial_authority_granted": False,
        }
    digest, bundle, verification = selected
    return {
        "schema_version": "constructionsight.native-arcgis-proof-review/v1",
        "configured": True,
        "available": True,
        "bundle_id": bundle.bundle_id,
        "bundle_sha256": digest,
        "source_key": bundle.source_key,
        "county": bundle.county,
        "assessment_status": bundle.assessment.status.value,
        "verification": verification,
        "network_executed": False,
        "source_database_mutated": False,
        "parcel_imported": False,
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
    }


def native_arcgis_proof_inventory(directory: Path) -> dict[str, Any]:
    """Use the original validated proof reader against the existing shared DB."""
    database = directory / "investigations.sqlite3"
    if not database.exists() and not database.is_symlink():
        return source_inspection(None, route="/api/source-parcel-proofs")
    return source_inspection(
        prepare_private_database(database, create=False),
        route="/api/source-parcel-proofs",
    )


def persist_reviewed_arcgis_proof(
    directory: Path,
    path: Path | None,
    payload: dict[str, Any],
    *,
    original_database: Path | None = None,
) -> dict[str, Any]:
    """Persist only a verified, SHA-bound original proof into the native store."""
    if set(payload) != {
        "expected_bundle_id", "expected_bundle_sha256",
        "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact offline ArcGIS proof review fields required")
    reason = payload["review_reason"]
    if (
        not isinstance(payload["expected_bundle_id"], str)
        or not isinstance(payload["expected_bundle_sha256"], str)
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
    ):
        raise ValueError("explicit reviewed proof identity and confirmation required")
    selected = _selected_proof(path)
    if selected is None:
        raise ValueError("no original bounded ArcGIS proof is configured")
    digest, bundle, _ = selected
    if (
        digest != payload["expected_bundle_sha256"]
        or bundle.bundle_id != payload["expected_bundle_id"]
    ):
        raise ValueError("retained ArcGIS proof changed; repeat independent review")
    database = prepare_private_database(
        directory / "investigations.sqlite3", create=False,
    )
    if original_database is not None and original_database.samefile(database):
        raise ValueError("original operator source database must remain separate")
    try:
        result = persist_authorized_arcgis_bundle(
            bundle=bundle,
            expected_bundle_id=bundle.bundle_id,
            database_url=database_url_from_path(database),
            authorization_reason=reason.strip(),
            caller_confirmation=True,
        )
        # A replayed effect receipt is not evidence of a current database row
        # after a restore. Re-read the exact original validated persisted chain.
        engine = create_operator_read_engine(database)
        try:
            with Session(engine, autoflush=False) as session:
                persisted = load_arcgis_bounded_proof_bundles(
                    session, source_key=bundle.source_key, county=bundle.county,
                )
                if sum(item.bundle_id == bundle.bundle_id for item in persisted) != 1:
                    raise ValueError("authorized ArcGIS proof is absent from current native store")
        finally:
            engine.dispose()
    except (
        AuthorizationDeniedError, ParcelArcGISOperatorServiceError, SQLAlchemyError,
    ) as exc:
        raise ValueError("governed ArcGIS proof persistence was not verified") from exc
    return {
        "schema_version": "constructionsight.native-arcgis-proof-persistence/v1",
        "bundle_id": bundle.bundle_id,
        "bundle_sha256": digest,
        "receipt": result.receipt.to_dict(),
        "authorization_audit_identity": result.authorization.decision.audit_identity,
        "persisted_in_shared_database": True,
        "network_executed": False,
        "original_source_database_mutated": False,
        "parcel_imported": False,
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
    }
