"""Native offline access to preserved SMARTS multi-source operator review.

Inputs are selected once by the local operator in an exact retained manifest.
No remote request, source promotion, project identity join or database mutation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from constructionsight.smarts_snapshot_diff import COUNTIES, MAX_CSV_BYTES
from constructionsight.smarts_source_review_cli import prepare_source_review
from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_SCHEMA = "constructionsight.smarts-source-review-inputs/v1"
_OPTIONS = ("previous", "current", "inspections", "violations", "enforcement")
_REQUIRED = frozenset({"schema_version", "previous", "current"})


def native_original_smarts_source_review(
    *, manifest: Path | None, county: str,
) -> dict[str, Any]:
    """Replay original combined source review with exact, unchanged retained files."""
    if county not in COUNTIES:
        raise ValueError("select one approved SMARTS county")
    if manifest is None:
        return {
            "schema_version": "constructionsight.native-smarts-source-review/v1",
            "available": False, "configured": False, "county": county,
            "read_only": True, "network_executed": False,
            "persistence_mutated": False, "commercial_authority_granted": False,
            "meaning": (
                "Configure a retained SMARTS source-review input manifest at startup. "
                "Absence of evidence is not evidence of no inspection or compliance activity."
            ),
        }
    raw = read_runtime_artifact(manifest, max_bytes=4_096)
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != _SCHEMA:
        raise ValueError("invalid configured original SMARTS source-review manifest")
    if not _REQUIRED.issubset(payload) or set(payload) - (
        _REQUIRED | set(_OPTIONS)
    ):
        raise ValueError("unknown or missing SMARTS retained source evidence slots")
    inputs: dict[str, Path] = {}
    for key in _OPTIONS:
        if key not in payload:
            continue
        filename = payload[key]
        if (
            not isinstance(filename, str)
            or not 1 <= len(filename) <= 160
            or Path(filename).name != filename
            or "/" in filename or "\\" in filename
            or filename in {".", ".."}
            or not filename.lower().endswith(".csv")
        ):
            raise ValueError(f"SMARTS {key} must name one sibling retained CSV")
        inputs[key] = manifest.parent / filename
    if len(set(inputs.values())) != len(inputs):
        raise ValueError("original SMARTS evidence files must remain distinct")
    hashes: dict[str, str] = {}
    for key, path in inputs.items():
        body = read_runtime_artifact(path, max_bytes=MAX_CSV_BYTES)
        hashes[key] = hashlib.sha256(body).hexdigest()
    result = prepare_source_review(
        county=county, previous=inputs["previous"], current=inputs["current"],
        inspections=inputs.get("inspections"), violations=inputs.get("violations"),
        enforcement=inputs.get("enforcement"),
    )
    for key, path in inputs.items():
        body = read_runtime_artifact(path, max_bytes=MAX_CSV_BYTES)
        if hashlib.sha256(body).hexdigest() != hashes[key]:
            raise ValueError("retained SMARTS CSV changed during original offline review")
    if read_runtime_artifact(manifest, max_bytes=4_096) != raw:
        raise ValueError("retained SMARTS input manifest changed during review")
    return {
        "schema_version": "constructionsight.native-smarts-source-review/v1",
        "available": True, "configured": True, "county": county,
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "retained_source_sha256": hashes,
        "original_source_review": result,
        "read_only": True, "network_executed": False,
        "persistence_mutated": False, "project_identity_verified": False,
        "physical_construction_verified": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Original offline facility, inspection and compliance source-corroboration "
            "review. Changes, regulatory events and candidate matches cannot independently "
            "establish physical construction, shared site identity or commercial readiness."
        ),
    }
