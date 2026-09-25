"""Bounded, handle-relative file loading for independently verified ArcGIS proofs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constructionsight.parcel_source_acquisition_bundle import verify_arcgis_bounded_proof_bundle
from constructionsight.parcel_source_acquisition_bundle_models import ParcelArcGISBoundedProofBundle
from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_MAX_BOUNDED_PROOF_FILE_BYTES = 64 * 1024 * 1024


def load_arcgis_bounded_proof_bundle(
    path: Path,
) -> ParcelArcGISBoundedProofBundle:
    """Load and independently verify one JSON proof bundle from disk."""

    try:
        raw = read_runtime_artifact(path, max_bytes=_MAX_BOUNDED_PROOF_FILE_BYTES)
        payload: Any = json.loads(raw)
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"cannot load ArcGIS bounded-proof bundle: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("ArcGIS bounded-proof bundle must be a JSON object")
    try:
        bundle = ParcelArcGISBoundedProofBundle.model_validate(payload)
    except ValueError as exc:
        raise ValueError("invalid ArcGIS bounded-proof bundle") from exc
    verify_arcgis_bounded_proof_bundle(bundle)
    return bundle
