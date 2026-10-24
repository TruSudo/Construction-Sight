"""Reviewed native handoff to original bounded CS-NET-004 ArcGIS probe.

No bulk collection, geometry, source promotion or identity inference. The
original service owns the remote request and cross-process durable allowance.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.command_center_ceqanet_acquisition import _profile
from constructionsight.legal import AccessDecision, evaluate_access
from constructionsight.operator_services.parcel_arcgis_service import (
    execute_authorized_arcgis_probe,
)
from constructionsight.parcel_source_acquisition_bundle import (
    verify_arcgis_bounded_proof_bundle,
)
from constructionsight.parcel_source_verification import (
    get_parcel_source_evidence,
    get_verified_parcel_source_profiles,
)
from constructionsight.parcel_source_verification_models import (
    ParcelSourceVerificationStatus,
)
from constructionsight.storage.runtime_artifacts import write_runtime_text

_FIELDS = {"source_key", "sample_size", "access_review"}
_TIMEOUT = 15.0
_MAX_PROOF_BYTES = 64 * 1024 * 1024


def _scope(payload: dict[str, Any]) -> tuple[Any, tuple[Any, ...], int, Any]:
    if not isinstance(payload, dict) or set(payload) != _FIELDS:
        raise ValueError("exact ArcGIS source, sample and access facts required")
    size = payload["sample_size"]
    if type(size) is not int or not 1 <= size <= 100:
        raise ValueError("original ArcGIS sample must be a bounded integer 1–100")
    source_key = payload["source_key"]
    if not isinstance(source_key, str):
        raise ValueError("exact existing ArcGIS source key required")
    profiles = {p.source_key: p for p in get_verified_parcel_source_profiles()}
    profile = profiles.get(source_key)
    if (
        profile is None
        or profile.status is not ParcelSourceVerificationStatus.VERIFIED_PREVIEW
        or not profile.public_access_verified
    ):
        raise ValueError("existing official verified-preview ArcGIS profile required")
    indexed = {x.evidence_id: x for x in get_parcel_source_evidence()}
    try:
        evidence = tuple(indexed[x] for x in profile.evidence_ids)
    except KeyError as exc:
        raise ValueError("original ArcGIS evidence/profile mismatch") from exc
    if any(x.source_key != source_key or x.county != profile.county for x in evidence):
        raise ValueError("original ArcGIS evidence/region mismatch")
    access = evaluate_access(_profile(profile.source_url, payload["access_review"]))
    return profile, evidence, size, access


def preview_original_arcgis_probe(
    directory: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Bind one reviewed fixed-source probe to existing original evidence."""
    profile, evidence, size, access = _scope(payload)
    digest = authorization_digest("native-original-arcgis-probe/v1", {
        "profile": profile.model_dump(mode="json"),
        "evidence": [x.model_dump(mode="json") for x in evidence],
        "sample_size": size,
        "timeout_seconds": _TIMEOUT,
        "current_access_review": payload["access_review"],
        "policy": "CS-NET-004",
    })
    filename = "arcgis-probe-" + hashlib.sha256(digest.encode()).hexdigest() + ".json"
    output = directory / "arcgis-bounded-proofs" / filename if directory else None
    blockers: list[str] = []
    if output is None:
        blockers.append("real private data directory not configured")
    elif output.exists() or output.is_symlink():
        blockers.append("original proof already retained for this exact reviewed scope")
    if access.decision is not AccessDecision.ALLOWED:
        blockers.append("current independently reviewed lawful ArcGIS access not allowed")
    return {
        "schema_version": "constructionsight.native-original-arcgis-probe-preview/v1",
        "available": output is not None,
        "may_request_approval": not blockers,
        "blockers": blockers,
        "source_key": profile.source_key,
        "profile_id": profile.profile_id,
        "county": profile.county,
        "historical_profile_observed_at": profile.observed_at.isoformat(),
        "existing_evidence_ids": list(profile.evidence_ids),
        "sample_size": size,
        "timeout_seconds": _TIMEOUT,
        "maximum_exact_requests": 5,
        "access_decision": access.decision.value,
        "expected_preview_digest": digest,
        "retained_output_file": filename,
        "network_executed": False,
        "bulk_acquisition_authorized": False,
        "parcel_imported": False,
        "commercial_authority_granted": False,
    }


def execute_reviewed_original_arcgis_probe(
    directory: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute original owned five-request effect after exact operator consent."""
    if not isinstance(payload, dict) or set(payload) != _FIELDS | {
        "expected_preview_digest", "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact original ArcGIS operator approval required")
    reason = payload["review_reason"]
    if (
        payload["caller_confirmation"] is not True
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2_000
        or not isinstance(payload["expected_preview_digest"], str)
    ):
        raise ValueError("explicit positive original ArcGIS probe approval required")
    selected = {key: payload[key] for key in _FIELDS}
    preview = preview_original_arcgis_probe(directory, selected)
    if (
        not preview["may_request_approval"]
        or preview["expected_preview_digest"] != payload["expected_preview_digest"]
    ):
        raise ValueError("original ArcGIS source approval denied or stale")
    assert directory is not None
    profile, evidence, size, _ = _scope(selected)
    output = directory / "arcgis-bounded-proofs" / preview["retained_output_file"]
    if output.is_symlink() or output.exists():
        raise ValueError("ArcGIS retained proof output occupied")
    original = execute_authorized_arcgis_probe(
        profile=profile,
        source_evidence=evidence,
        sample_size=size,
        timeout_seconds=_TIMEOUT,
        authorization_reason=reason.strip(),
        caller_confirmation=True,
    )
    bundle = original.bundle
    proof = verify_arcgis_bounded_proof_bundle(bundle)
    if (
        not proof.valid
        or bundle.profile.profile_id != profile.profile_id
        or bundle.source_key != profile.source_key
        or bundle.network_request_count != 5
        or bundle.bulk_run_authorized
    ):
        raise ValueError("original ArcGIS proof did not independently verify")
    raw = json.dumps(bundle.to_dict(), sort_keys=True, indent=2) + "\n"
    write_runtime_text(output, raw, overwrite=False, max_bytes=_MAX_PROOF_BYTES)
    return {
        "schema_version": "constructionsight.native-original-arcgis-probe-result/v1",
        "source_key": bundle.source_key,
        "bundle_id": bundle.bundle_id,
        "bundle_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "retained_proof_path": str(output),
        "retained_output_file": output.name,
        "original_independent_verification": proof.to_dict(),
        "original_authorization_audit_identity": (
            original.authorization.decision.audit_identity
        ),
        "reviewed_preview_digest": preview["expected_preview_digest"],
        "retained_proof_written": True,
        "network_executed": True,
        "exact_request_count": 5,
        "native_proof_persisted": False,
        "parcel_imported": False,
        "bulk_acquisition_authorized": False,
        "commercial_authority_granted": False,
    }
