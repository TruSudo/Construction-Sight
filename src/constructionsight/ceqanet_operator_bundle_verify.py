"""CEQAnet operator bundle verification service.

This module verifies a previously written CEQAnet operator bundle manifest against
files on disk. It performs no network requests, database access, or persistence
mutation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

VerificationStatus = Literal["verified", "missing", "mismatch"]


@dataclass(frozen=True)
class CeqanetBundleArtifactVerification:
    """Verification result for one manifest-listed bundle artifact."""

    filename: str
    artifact_type: str
    expected_sha256: str
    actual_sha256: str | None
    expected_byte_count: int | None
    actual_byte_count: int | None
    status: VerificationStatus

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe artifact verification payload."""

        return {
            "filename": self.filename,
            "artifact_type": self.artifact_type,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "expected_byte_count": self.expected_byte_count,
            "actual_byte_count": self.actual_byte_count,
            "status": self.status,
        }


@dataclass(frozen=True)
class CeqanetBundleVerification:
    """Verification result for one CEQAnet operator bundle."""

    bundle_dir: Path
    manifest_path: Path
    artifacts: tuple[CeqanetBundleArtifactVerification, ...]
    malformed_artifacts: tuple[dict[str, object], ...]

    @property
    def verified_count(self) -> int:
        """Return verified artifact count."""

        return sum(1 for artifact in self.artifacts if artifact.status == "verified")

    @property
    def missing_count(self) -> int:
        """Return missing artifact count."""

        return sum(1 for artifact in self.artifacts if artifact.status == "missing")

    @property
    def mismatch_count(self) -> int:
        """Return mismatched artifact count."""

        return sum(1 for artifact in self.artifacts if artifact.status == "mismatch")

    @property
    def passed(self) -> bool:
        """Return whether all manifest-listed artifacts verified."""

        return self.missing_count == 0 and self.mismatch_count == 0 and not self.malformed_artifacts

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe bundle verification payload."""

        return {
            "metadata": {
                "schema_version": "ceqanet_operator_bundle_verification.v1",
                "bundle_dir": str(self.bundle_dir),
                "manifest_path": str(self.manifest_path),
                "artifact_count": len(self.artifacts),
                "verified_count": self.verified_count,
                "missing_count": self.missing_count,
                "mismatch_count": self.mismatch_count,
                "malformed_artifact_count": len(self.malformed_artifacts),
                "passed": self.passed,
                "network_executed": False,
                "database_opened": False,
                "persistence_mutated": False,
            },
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "malformed_artifacts": list(self.malformed_artifacts),
        }


def verify_ceqanet_operator_bundle(
    *,
    bundle_dir: Path,
    manifest_path: Path | None = None,
) -> CeqanetBundleVerification:
    """Verify a CEQAnet operator bundle manifest against local files."""

    resolved_manifest_path = manifest_path or bundle_dir / "manifest.json"
    manifest = _load_manifest(resolved_manifest_path)
    artifact_entries = _artifact_entries(manifest)

    verified_artifacts: list[CeqanetBundleArtifactVerification] = []
    malformed_artifacts: list[dict[str, object]] = []

    for index, entry in enumerate(artifact_entries):
        if not isinstance(entry, dict):
            malformed_artifacts.append({"index": index, "reason": "artifact is not an object"})
            continue
        artifact = _verify_artifact_entry(bundle_dir, index=index, entry=cast(dict[str, Any], entry))
        if artifact is None:
            malformed_artifacts.append(
                {"index": index, "reason": "artifact missing filename, artifact_type, or sha256"}
            )
            continue
        verified_artifacts.append(artifact)

    return CeqanetBundleVerification(
        bundle_dir=bundle_dir,
        manifest_path=resolved_manifest_path,
        artifacts=tuple(verified_artifacts),
        malformed_artifacts=tuple(malformed_artifacts),
    )


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and validate bundle manifest JSON."""

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Bundle manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Bundle manifest is not valid JSON: {manifest_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Bundle manifest must contain a JSON object.")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Bundle manifest must contain metadata.")
    if metadata.get("schema_version") != "ceqanet_operator_bundle.v1":
        raise ValueError("Bundle manifest schema_version must be ceqanet_operator_bundle.v1.")
    return cast(dict[str, Any], payload)


def _artifact_entries(manifest: dict[str, Any]) -> list[object]:
    """Return manifest artifact entries."""

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Bundle manifest must contain artifacts list.")
    return artifacts


def _verify_artifact_entry(
    bundle_dir: Path,
    *,
    index: int,
    entry: dict[str, Any],
) -> CeqanetBundleArtifactVerification | None:
    """Verify one manifest artifact entry."""

    filename = _string_or_none(entry.get("filename"))
    artifact_type = _string_or_none(entry.get("artifact_type"))
    expected_sha256 = _string_or_none(entry.get("sha256"))
    expected_byte_count = _int_or_none(entry.get("byte_count"))
    if filename is None or artifact_type is None or expected_sha256 is None:
        return None

    artifact_path = bundle_dir / filename
    if not artifact_path.exists():
        return CeqanetBundleArtifactVerification(
            filename=filename,
            artifact_type=artifact_type,
            expected_sha256=expected_sha256,
            actual_sha256=None,
            expected_byte_count=expected_byte_count,
            actual_byte_count=None,
            status="missing",
        )

    data = artifact_path.read_bytes()
    actual_sha256 = hashlib.sha256(data).hexdigest()
    actual_byte_count = len(data)
    status: VerificationStatus = "verified"
    if actual_sha256 != expected_sha256 or (
        expected_byte_count is not None and actual_byte_count != expected_byte_count
    ):
        status = "mismatch"

    return CeqanetBundleArtifactVerification(
        filename=filename,
        artifact_type=artifact_type,
        expected_sha256=expected_sha256,
        actual_sha256=actual_sha256,
        expected_byte_count=expected_byte_count,
        actual_byte_count=actual_byte_count,
        status=status,
    )


def _string_or_none(value: object) -> str | None:
    """Return non-empty string value or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _int_or_none(value: object) -> int | None:
    """Return integer values while rejecting bools."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
