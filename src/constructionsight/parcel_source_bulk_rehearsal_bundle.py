"""Build, save, load, and independently verify complete rehearsal bundles."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from datetime import UTC, datetime
from itertools import chain
from pathlib import Path
from typing import Any, Protocol

from constructionsight.parcel_source_acquisition import build_arcgis_bulk_manifest
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISCapabilitySnapshot,
    digest_identity,
)
from constructionsight.parcel_source_bulk_rehearsal import (
    ParcelArcGISBulkRehearsalExecution,
)
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    ParcelArcGISBulkArtifactReceipt,
)
from constructionsight.parcel_source_bulk_rehearsal_bundle_models import (
    ParcelArcGISBulkPortableArtifact,
    ParcelArcGISBulkRehearsalProofBundle,
    ParcelArcGISBulkRehearsalProofVerification,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    ParcelArcGISBulkRehearsalPlan,
    build_arcgis_bulk_rehearsal_plan,
)

_MAX_PORTABLE_PROOF_FILE_BYTES = 256 * 1024 * 1024

_DEFAULT_LIMITATIONS = (
    "A complete rehearsal proof does not authorize parcel import or recurring collection.",
    "The bundle proves only the exact snapshot, plan, manifest, and response bytes it contains.",
    "Verification does not establish legal title, survey accuracy, or source-profile promotion.",
)


class ParcelArcGISBulkArtifactReader(Protocol):
    """Read boundary for exact successful response artifacts."""

    def read(self, receipt: ParcelArcGISBulkArtifactReceipt) -> bytes:
        """Reload and validate the exact bytes described by one receipt."""

        ...


def build_arcgis_bulk_rehearsal_proof_bundle(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
    execution: ParcelArcGISBulkRehearsalExecution,
    artifact_reader: ParcelArcGISBulkArtifactReader,
    *,
    limitations: tuple[str, ...] = _DEFAULT_LIMITATIONS,
    created_at: datetime | None = None,
) -> ParcelArcGISBulkRehearsalProofBundle:
    """Bind one complete execution and every exact response into a portable artifact."""

    _require_execution_scope(snapshot, plan, execution)
    artifacts = tuple(
        _portable_artifact(receipt, artifact_reader.read(receipt))
        for receipt in execution.artifact_receipts
    )
    return _build_bundle_from_portable_artifacts(
        snapshot,
        plan,
        execution,
        artifacts,
        limitations=limitations,
        created_at=created_at or datetime.now(UTC),
    )


def verify_arcgis_bulk_rehearsal_proof_bundle(
    bundle: ParcelArcGISBulkRehearsalProofBundle,
    *,
    verified_at: datetime | None = None,
) -> ParcelArcGISBulkRehearsalProofVerification:
    """Reparse every exact body and rebuild all derived proof without network access."""

    effective_verified_at = verified_at or datetime.now(UTC)
    if bundle.created_at < bundle.manifest.completed_at:
        raise ValueError(
            "ArcGIS rehearsal proof bundle creation cannot precede manifest completion"
        )
    if effective_verified_at < bundle.created_at:
        raise ValueError(
            "ArcGIS rehearsal proof verification time cannot precede bundle creation"
        )
    rebuilt_plan = build_arcgis_bulk_rehearsal_plan(
        bundle.snapshot,
        generated_at=bundle.plan.generated_at,
        page_size=bundle.plan.page_size,
        checkpoint_after_pages=bundle.plan.checkpoint_after_pages,
        injected_retry_page_index=bundle.plan.injected_retry_page_index,
        max_attempts=bundle.plan.max_attempts,
        retry_delays_seconds=bundle.plan.retry_delays_seconds,
        timeout_seconds=bundle.plan.timeout_seconds,
        max_response_bytes=bundle.plan.max_response_bytes,
        retry_status_codes=bundle.plan.retry_status_codes,
        accepted_media_types=bundle.plan.accepted_media_types,
    )
    if rebuilt_plan != bundle.plan:
        raise ValueError("ArcGIS rehearsal proof plan failed independent recomputation")
    rebuilt_manifest = build_arcgis_bulk_manifest(
        bundle.snapshot,
        started_at=bundle.manifest.started_at,
        completed_at=bundle.manifest.completed_at,
        starting_count=bundle.manifest.starting_count,
        ending_count=bundle.manifest.ending_count,
        rehearsal_evidence=bundle.manifest.rehearsal_evidence,
    )
    if rebuilt_manifest != bundle.manifest:
        raise ValueError("ArcGIS rehearsal proof manifest failed independent recomputation")
    receipts = tuple(_artifact_receipt(artifact) for artifact in bundle.artifacts)
    rebuilt_execution = ParcelArcGISBulkRehearsalExecution(
        manifest=rebuilt_manifest,
        checkpoint_reloaded=bundle.checkpoint_reloaded,
        artifact_receipts=receipts,
        starting_count_response_digest=bundle.artifacts[0].response_digest,
        ending_count_response_digest=bundle.artifacts[-1].response_digest,
    )
    rebuilt_bundle = _build_bundle_from_portable_artifacts(
        bundle.snapshot,
        rebuilt_plan,
        rebuilt_execution,
        bundle.artifacts,
        limitations=bundle.limitations,
        created_at=bundle.created_at,
    )
    if rebuilt_bundle != bundle:
        raise ValueError("ArcGIS rehearsal proof bundle failed independent recomputation")
    candidate = ParcelArcGISBulkRehearsalProofVerification.model_construct(
        verification_id=(
            "parcel-arcgis-bulk-rehearsal-proof-verification:" + ("0" * 64)
        ),
        bundle_id=bundle.bundle_id,
        source_key=bundle.source_key,
        county=bundle.county,
        manifest_id=bundle.manifest.manifest_id,
        artifact_count=len(bundle.artifacts),
        plan_recomputed=True,
        manifest_recomputed=True,
        response_bytes_recomputed=True,
        object_ids_recomputed=True,
        valid=True,
        bulk_run_authorized=False,
        next_action=(
            "retain the verified rehearsal proof and conduct a separate source-profile "
            "promotion review before any import or recurring collection"
        ),
        verified_at=effective_verified_at,
    )
    payload = candidate.model_dump(
        mode="json",
        exclude={"verification_id", "verified_at"},
    )
    return ParcelArcGISBulkRehearsalProofVerification.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "verification_id": digest_identity(
                "parcel-arcgis-bulk-rehearsal-proof-verification",
                payload,
            ),
        }
    )


def save_arcgis_bulk_rehearsal_proof_bundle(
    bundle: ParcelArcGISBulkRehearsalProofBundle,
    path: Path,
    *,
    expected_bundle_id: str,
) -> None:
    """Atomically save an independently verified bundle under an exact expected ID."""

    if expected_bundle_id != bundle.bundle_id:
        raise ValueError("ArcGIS rehearsal proof expected bundle identity does not match")
    verify_arcgis_bulk_rehearsal_proof_bundle(bundle)
    if path.is_symlink():
        raise ValueError("ArcGIS rehearsal proof output cannot be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = load_arcgis_bulk_rehearsal_proof_bundle(path)
        if existing != bundle:
            raise ValueError("ArcGIS rehearsal proof path contains conflicting content")
        return

    # A fresh unique temporary file prevents concurrent writers from sharing an
    # intermediate path. No partial or oversized proof is published.
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"))
    byte_count = 0
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=".arcgis-rehearsal-proof-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            for fragment in chain(encoder.iterencode(bundle.to_dict()), ("\n",)):
                for start in range(0, len(fragment), 16_384):
                    chunk = fragment[start : start + 16_384].encode("utf-8")
                    byte_count += len(chunk)
                    if byte_count > _MAX_PORTABLE_PROOF_FILE_BYTES:
                        raise ValueError(
                            "ArcGIS rehearsal proof exceeds the file byte limit"
                        )
                    temporary.write(chunk)
            temporary.flush()
            os.fsync(temporary.fileno())
        # An atomic create-only link refuses to replace a proof published by
        # another writer after our earlier path.exists() check.
        try:
            os.link(temporary_path, path, follow_symlinks=False)
        except FileExistsError:
            if path.is_symlink():
                raise ValueError(
                    "ArcGIS rehearsal proof output cannot be a symlink"
                ) from None
            existing = load_arcgis_bulk_rehearsal_proof_bundle(path)
            if existing != bundle:
                raise ValueError(
                    "ArcGIS rehearsal proof path contains conflicting content"
                ) from None
            return
        # The linked proof now has an authoritative path; removing its original
        # temporary name does not change the published inode.
        temporary_path.unlink()
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_arcgis_bulk_rehearsal_proof_bundle(
    path: Path,
) -> ParcelArcGISBulkRehearsalProofBundle:
    """Load and independently verify one portable proof bundle from disk."""

    try:
        with path.open("rb") as proof_file:
            raw = proof_file.read(_MAX_PORTABLE_PROOF_FILE_BYTES + 1)
        if len(raw) > _MAX_PORTABLE_PROOF_FILE_BYTES:
            raise ValueError("ArcGIS rehearsal proof bundle exceeds the file byte limit")
        payload: Any = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot load ArcGIS rehearsal proof bundle: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("ArcGIS rehearsal proof bundle must be a JSON object")
    try:
        bundle = ParcelArcGISBulkRehearsalProofBundle.model_validate(payload)
    except ValueError as exc:
        raise ValueError("invalid ArcGIS rehearsal proof bundle") from exc
    verify_arcgis_bulk_rehearsal_proof_bundle(bundle)
    return bundle


def _build_bundle_from_portable_artifacts(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
    execution: ParcelArcGISBulkRehearsalExecution,
    artifacts: tuple[ParcelArcGISBulkPortableArtifact, ...],
    *,
    limitations: tuple[str, ...],
    created_at: datetime,
) -> ParcelArcGISBulkRehearsalProofBundle:
    canonical_limitations = tuple(sorted(set(limitations), key=str.casefold))
    candidate = ParcelArcGISBulkRehearsalProofBundle.model_construct(
        bundle_id="parcel-arcgis-bulk-rehearsal-proof-bundle:" + ("0" * 64),
        source_key=snapshot.source_key,
        county=snapshot.county,
        snapshot=snapshot,
        plan=plan,
        manifest=execution.manifest,
        checkpoint_reloaded=execution.checkpoint_reloaded,
        artifacts=artifacts,
        bulk_run_authorized=False,
        limitations=canonical_limitations,
        created_at=created_at,
    )
    payload = candidate.identity_payload()
    return ParcelArcGISBulkRehearsalProofBundle.model_validate(
        {
            **candidate.to_dict(),
            "bundle_id": digest_identity(
                "parcel-arcgis-bulk-rehearsal-proof-bundle",
                payload,
            ),
        }
    )


def _portable_artifact(
    receipt: ParcelArcGISBulkArtifactReceipt,
    response_body: bytes,
) -> ParcelArcGISBulkPortableArtifact:
    return ParcelArcGISBulkPortableArtifact(
        kind=receipt.kind,
        sequence_index=receipt.sequence_index,
        response_digest=receipt.response_digest,
        response_size=receipt.response_size,
        artifact_reference=receipt.artifact_reference,
        response_body_base64=base64.b64encode(response_body).decode("ascii"),
    )


def _artifact_receipt(
    artifact: ParcelArcGISBulkPortableArtifact,
) -> ParcelArcGISBulkArtifactReceipt:
    return ParcelArcGISBulkArtifactReceipt(
        kind=artifact.kind,
        sequence_index=artifact.sequence_index,
        response_digest=artifact.response_digest,
        response_size=artifact.response_size,
        artifact_reference=artifact.artifact_reference,
    )


def _require_execution_scope(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
    execution: ParcelArcGISBulkRehearsalExecution,
) -> None:
    manifest = execution.manifest
    if (
        plan.snapshot_id != snapshot.snapshot_id
        or manifest.snapshot_id != snapshot.snapshot_id
        or plan.profile_id != snapshot.profile_id
        or manifest.profile_id != snapshot.profile_id
        or plan.source_key != snapshot.source_key
        or manifest.source_key != snapshot.source_key
        or plan.county != snapshot.county
        or manifest.county != snapshot.county
        or plan.page_size != manifest.page_size
    ):
        raise ValueError("ArcGIS rehearsal proof execution scope does not match plan")
