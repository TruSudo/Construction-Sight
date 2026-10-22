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
from constructionsight.parcel_schema_models import (
    ParcelObservedFieldType,
    ParcelSchemaField,
    ParcelSchemaPreviewInput,
)
from constructionsight.parcel_schema_preview import preview_schema
from constructionsight.parcel_source_models import ParcelGeometrySupport
from constructionsight.parcel_source_registry import get_parcel_sources
from constructionsight.storage.database import (
    database_url_from_path,
    prepare_private_database,
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


def _observed_arcgis_schema(
    bundle: ParcelArcGISBoundedProofBundle,
) -> dict[str, Any]:
    """Review immutable ArcGIS metadata with the original schema-preview service.

    Source-registry mappings are expectations; the snapshot is historical
    observed metadata. No sampled parcel row or project identity is inferred.
    """
    source = next(
        (item for item in get_parcel_sources() if item.source_key == bundle.source_key),
        None,
    )
    if (
        source is None
        or source.source_url != bundle.snapshot.layer_url
        or source.coverage.county != bundle.county
    ):
        raise ValueError("ArcGIS proof does not match the current registered parcel source")

    snapshot = bundle.snapshot
    original_input = ParcelSchemaPreviewInput(
        source_key=source.source_key,
        source_name=source.source_name,
        source_format=source.source_format,
        observed_fields=[
            ParcelSchemaField(
                source_field=field.name,
                observed_type=ParcelObservedFieldType.UNKNOWN,
                description=f"Observed ArcGIS field type: {field.field_type}",
                nullable=field.nullable,
            )
            for field in snapshot.fields
        ],
        constant_fields=list(source.constant_fields),
        # Never claim that the historical polygon label proves actual geometry
        # was captured; only the ArcGIS geometry-type string is observed.
        geometry_support=ParcelGeometrySupport.UNKNOWN,
        spatial_reference=snapshot.spatial_reference,
        source_url=source.source_url,
        limitations=[
            "This report describes retained ArcGIS metadata, not imported parcel rows.",
            "Original inferred role matches are proposals, not verified source-to-site identities.",
            "The observed source schema can change after its recorded observation time.",
        ],
    )
    report = preview_schema(original_input)
    advertised_names = {field.name.casefold() for field in snapshot.fields}
    expected_names = {mapping.source_field.casefold() for mapping in source.field_mappings}
    return {
        "schema_version": "constructionsight.native-arcgis-observed-schema/v1",
        "original_schema_preview_service_reused": True,
        "original_source_key": source.source_key,
        "bundle_id": bundle.bundle_id,
        "snapshot_id": snapshot.snapshot_id,
        "schema_fingerprint": snapshot.schema_fingerprint,
        "metadata_projection_digest": snapshot.metadata_projection_digest,
        "observed_at": snapshot.observed_at.isoformat(),
        "observed_geometry_type": snapshot.geometry_type,
        "observed_fields": [field.model_dump(mode="json") for field in snapshot.fields],
        "unobserved_expected_fields": sorted(expected_names - advertised_names),
        "additional_observed_fields": sorted(advertised_names - expected_names),
        "original_schema_preview": report.model_dump(
            mode="json", exclude={"created_at"},
        ),
        "network_executed": False,
        "parcel_rows_observed": False,
        "parcel_imported": False,
        "project_identity_established": False,
        "commercial_authority_granted": False,
    }


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
        "observed_schema": _observed_arcgis_schema(bundle),
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
    existing = native_arcgis_proof_inventory(directory)
    if existing["total"] >= 50 and not any(
        item["bundle_id"] == bundle.bundle_id for item in existing["bundles"]
    ):
        raise ValueError("native ArcGIS proof inventory exceeds 50-item limit")
    try:
        result = persist_authorized_arcgis_bundle(
            bundle=bundle,
            expected_bundle_id=bundle.bundle_id,
            database_url=database_url_from_path(database),
            authorization_reason=reason.strip(),
            caller_confirmation=True,
        )
        current = native_arcgis_proof_inventory(directory)
        if sum(item["bundle_id"] == bundle.bundle_id for item in current["bundles"]) != 1:
            raise ValueError("verified ArcGIS proof absent from current native store")
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
