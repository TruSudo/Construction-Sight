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
from constructionsight.parcel_row_preview import preview_rows
from constructionsight.parcel_row_preview_models import ParcelRowPreviewInput
from constructionsight.parcel_schema_models import (
    ParcelFieldRoleMatch,
    ParcelObservedFieldType,
    ParcelSchemaField,
    ParcelSchemaPreviewInput,
)
from constructionsight.parcel_schema_preview import preview_schema
from constructionsight.parcel_source_acquisition_bundle import (
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_acquisition_bundle_models import (
    ParcelArcGISBoundedProofBundle,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISProbeKind,
    digest_identity,
)
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
        raise ValueError(
            "ArcGIS proof does not match the current registered parcel source"
        )

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
            "Original inferred role matches are proposals, not verified "
            "source-to-site identities.",
            "The observed source schema may change after its recorded observation.",
        ],
    )
    report = preview_schema(original_input)
    advertised_names = {field.name.casefold() for field in snapshot.fields}
    # ArcGIS feature geometry is a documented result member, not a field in
    # the layer attribute schema. Do not manufacture a missing-field warning.
    expected_names = {
        mapping.source_field.casefold() for mapping in source.field_mappings
        if mapping.source_field.casefold() != "geometry"
    }
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


def preview_arcgis_proof_bound_rows(
    path: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Run the original row preview against one exact historical ArcGIS schema.

    Only the *schema* is independently verified. The operator's manually
    supplied row values remain unverified and cannot be persisted here.
    """
    required = {
        "source_key", "expected_bundle_id", "expected_bundle_sha256",
        "expected_snapshot_id", "rows",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("exact ArcGIS proof identity and sample rows required")
    selected = _selected_proof(path)
    if selected is None:
        raise ValueError("a retained independently verified ArcGIS proof is required")
    digest, bundle, _ = selected
    if (
        type(payload["source_key"]) is not str
        or payload["source_key"] != bundle.source_key
        or payload["expected_bundle_id"] != bundle.bundle_id
        or payload["expected_bundle_sha256"] != digest
        or payload["expected_snapshot_id"] != bundle.snapshot.snapshot_id
    ):
        raise ValueError("ArcGIS proof changed or source/snapshot identity disagrees")

    # This also validates exact current registry scope and official source URL.
    _observed_arcgis_schema(bundle)
    source = next(
        item for item in get_parcel_sources()
        if item.source_key == bundle.source_key
    )
    names = {field.name for field in bundle.snapshot.fields}
    mapped = [
        item for item in source.field_mappings if item.source_field in names
    ]
    allowed = {item.source_field for item in mapped}
    rows = payload["rows"]
    if type(rows) is not list or not 1 <= len(rows) <= 20:
        raise ValueError("ArcGIS sample must contain 1 to 20 bounded rows")
    cumulative = 0
    for row in rows:
        if type(row) is not dict or not row or len(row) > len(allowed):
            raise ValueError("ArcGIS sample rows require mapped observed fields")
        if any(type(key) is not str or key not in allowed for key in row):
            raise ValueError("sample contains unobserved or unregistered ArcGIS field")
        if any(type(value) is not str for value in row.values()):
            raise ValueError("ArcGIS sample values must be text; no implicit coercion")
        cumulative += sum(
            len(key.encode("utf-8")) + len(value.encode("utf-8"))
            for key, value in row.items()
        )
        if cumulative > 32_000:
            raise ValueError("ArcGIS preview exceeds 32 KB payload budget")
    original_input = ParcelRowPreviewInput(
        source_key=source.source_key,
        source_name=source.source_name,
        source_format=source.source_format,
        field_role_matches=[
            ParcelFieldRoleMatch(
                source_field=item.source_field,
                field_role=item.field_role,
                match_reason="exact registered field in independently verified metadata",
                confidence_score=95,
                required_role=item.required,
            )
            for item in mapped
        ],
        constant_fields=list(source.constant_fields),
        rows=rows,
        geometry_support=ParcelGeometrySupport.UNKNOWN,
        spatial_reference=bundle.snapshot.spatial_reference,
        source_url=source.source_url,
        limitations=[
            "Manual sample rows have no independent source-response provenance.",
            "Verified schema is historical and does not establish current fields.",
            "Ready-for-record-model denotes parsing only; no import is authorized.",
        ],
    )
    result = preview_rows(original_input)
    return {
        "schema_version": "constructionsight.native-arcgis-bound-row-preview/v1",
        "original_row_preview_service_reused": True,
        "bundle_id": bundle.bundle_id,
        "bundle_sha256": digest,
        "snapshot_id": bundle.snapshot.snapshot_id,
        "schema_fingerprint": bundle.snapshot.schema_fingerprint,
        "source_key": source.source_key,
        "schema_verified": True,
        "manual_rows_independently_verified": False,
        "rows_persisted": False,
        "network_executed": False,
        "parcel_import_authorized": False,
        "project_identity_verified": False,
        "commercial_authority_granted": False,
        "report": result.model_dump(mode="json", exclude={"created_at"}),
    }


def preview_arcgis_proof_record_request(
    path: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Prepare one official source-row request from a verified bounded ID sample.

    The original four-request probe returns OBJECTIDs only. This method cannot
    acquire parcel attributes, use a user-supplied URL, or grant access rights.
    """
    required = {
        "source_key", "expected_bundle_id", "expected_bundle_sha256",
        "expected_snapshot_id", "object_id",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise ValueError("exact retained ArcGIS scope and object ID required")
    selected = _selected_proof(path)
    if selected is None:
        raise ValueError("no verified historical ArcGIS probe is configured")
    digest, bundle, _ = selected
    if (
        type(payload["source_key"]) is not str
        or payload["source_key"] != bundle.source_key
        or payload["expected_bundle_id"] != bundle.bundle_id
        or payload["expected_bundle_sha256"] != digest
        or payload["expected_snapshot_id"] != bundle.snapshot.snapshot_id
    ):
        raise ValueError("stale, mismatched or substituted ArcGIS proof identity")
    schema = _observed_arcgis_schema(bundle)
    snapshot = bundle.snapshot
    object_id = payload["object_id"]
    if type(object_id) is not int or not 0 < object_id <= 2**53 - 1:
        raise ValueError("one positive, exact ArcGIS integer object ID required")
    observed_ids = sorted({
        value
        for observation in bundle.observations
        if observation.kind in (
            ParcelArcGISProbeKind.INITIAL_PAGE,
            ParcelArcGISProbeKind.NEXT_PAGE,
        )
        for value in observation.object_ids
    })
    if object_id not in observed_ids:
        raise ValueError("selected ArcGIS object ID is absent from verified probe")
    source = next(
        item for item in get_parcel_sources()
        if item.source_key == bundle.source_key
    )
    observed_fields = {item.name for item in snapshot.fields}
    attribute_fields = sorted({
        item.source_field
        for item in source.field_mappings
        if item.source_field in observed_fields
        and item.source_field.casefold() != "geometry"
    })
    if (
        snapshot.object_id_field not in attribute_fields
        or not any(
            item.field_role.value == "apn" and item.source_field in attribute_fields
            for item in source.field_mappings
        )
    ):
        raise ValueError("registered object ID and APN fields must be observed")
    parameters = {
        "f": "json",
        "objectIds": str(object_id),
        "outFields": ",".join(attribute_fields),
        "returnGeometry": "false",
    }
    digest_payload = {
        "bundle_id": bundle.bundle_id,
        "bundle_sha256": digest,
        "snapshot_id": snapshot.snapshot_id,
        "source_key": bundle.source_key,
        "object_id": object_id,
        "query_url": snapshot.layer_url.rstrip("/") + "/query",
        "parameters": parameters,
    }
    return {
        "schema_version": "constructionsight.arcgis-proof-record-plan/v1",
        "plan_id": digest_identity("arcgis-proof-record-plan", digest_payload),
        **digest_payload,
        "observed_object_ids": observed_ids[:200],
        "observed_field_schema_verified": schema["original_schema_preview_service_reused"],
        "operator_access_review_required": True,
        "network_executed": False,
        "attributes_observed": False,
        "source_row_provenance_verified": False,
        "parcel_persisted": False,
        "site_identity_verified": False,
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
