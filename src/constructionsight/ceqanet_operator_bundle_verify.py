"""CEQAnet operator bundle verification service.

This module verifies a previously written CEQAnet operator bundle manifest against
files on disk. It performs no network requests, database access, or persistence
mutation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Literal, cast

from constructionsight.storage.runtime_artifacts import open_runtime_artifact

_MAX_BUNDLE_MANIFEST_BYTES = 1024 * 1024
_MAX_BUNDLE_ARTIFACTS = 128
_MAX_BUNDLE_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_BUNDLE_TOTAL_BYTES = 64 * 1024 * 1024
_BUNDLE_READ_CHUNK_BYTES = 64 * 1024

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
    # The exact manifest byte snapshot used for this verification's artifact inventory.
    manifest_byte_count: int
    manifest_sha256: str
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

        return (
            self.missing_count == 0
            and self.mismatch_count == 0
            and not self.malformed_artifacts
        )

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

    if bundle_dir.is_symlink() or not bundle_dir.is_dir():
        raise ValueError("Bundle root must be a real directory")
    root = bundle_dir.resolve(strict=True)
    resolved_manifest_path = manifest_path or bundle_dir / "manifest.json"
    _require_contained_bundle_file(resolved_manifest_path, root=root)
    manifest, manifest_bytes = _load_manifest(resolved_manifest_path)
    artifact_entries = _artifact_entries(manifest)
    if len(artifact_entries) > _MAX_BUNDLE_ARTIFACTS:
        raise ValueError("Bundle manifest exceeds artifact entry limit")
    remaining_bytes = [_MAX_BUNDLE_TOTAL_BYTES]

    verified_artifacts: list[CeqanetBundleArtifactVerification] = []
    malformed_artifacts: list[dict[str, object]] = []
    seen_filenames: set[str] = set()
    metadata = manifest["metadata"]
    if "artifact_count" in metadata and (
        type(metadata["artifact_count"]) is not int
        or metadata["artifact_count"] != len(artifact_entries)
    ):
        malformed_artifacts.append(
            {"index": -1, "reason": "manifest artifact_count mismatch"}
        )

    for index, entry in enumerate(artifact_entries):
        if not isinstance(entry, dict):
            malformed_artifacts.append({"index": index, "reason": "artifact is not an object"})
            continue
        artifact = _verify_artifact_entry(
            bundle_dir,
            entry=cast(dict[str, Any], entry),
            remaining_bytes=remaining_bytes,
            root=root,
        )
        if artifact is None:
            malformed_artifacts.append(
                {"index": index, "reason": "artifact missing filename, artifact_type, or sha256"}
            )
            continue
        if artifact.filename in seen_filenames:
            malformed_artifacts.append(
                {"index": index, "reason": "duplicate artifact filename"}
            )
        seen_filenames.add(artifact.filename)
        verified_artifacts.append(artifact)

    return CeqanetBundleVerification(
        bundle_dir=bundle_dir,
        manifest_path=resolved_manifest_path,
        manifest_byte_count=len(manifest_bytes),
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        artifacts=tuple(verified_artifacts),
        malformed_artifacts=tuple(malformed_artifacts),
    )


def _require_contained_bundle_file(path: Path, *, root: Path) -> None:
    """Reject symlinks and names outside the canonical bundle directory."""

    if path.is_symlink() or path.parent.resolve(strict=True) != root:
        raise ValueError("Bundle evidence path must be contained and not a symlink")
    if path.exists() and path.resolve(strict=True).parent != root:
        raise ValueError("Bundle evidence path escapes the intended root")


@contextmanager
def _open_regular_bundle_file(path: Path) -> Iterator[BinaryIO]:
    """Read bundle evidence through the shared complete-path no-follow boundary."""

    with open_runtime_artifact(path) as stream:
        yield stream


def _load_manifest(manifest_path: Path) -> tuple[dict[str, Any], bytes]:
    """Load and validate bundle manifest JSON."""

    try:
        with _open_regular_bundle_file(manifest_path) as manifest_file:
            manifest_bytes = manifest_file.read(_MAX_BUNDLE_MANIFEST_BYTES + 1)
        if len(manifest_bytes) > _MAX_BUNDLE_MANIFEST_BYTES:
            raise ValueError("Bundle manifest exceeds inspection byte limit")
        payload = json.loads(manifest_bytes.decode("utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Bundle manifest not found: {manifest_path}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"Bundle manifest is not valid UTF-8 JSON: {manifest_path}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Bundle manifest must contain a JSON object.")
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Bundle manifest must contain metadata.")
    if metadata.get("schema_version") != "ceqanet_operator_bundle.v1":
        raise ValueError(
            "Bundle manifest schema_version must be ceqanet_operator_bundle.v1."
        )
    return cast(dict[str, Any], payload), manifest_bytes


def _artifact_entries(manifest: dict[str, Any]) -> list[object]:
    """Return manifest artifact entries."""

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Bundle manifest must contain artifacts list.")
    return artifacts


def _verify_artifact_entry(
    bundle_dir: Path,
    *,
    entry: dict[str, Any],
    remaining_bytes: list[int],
    root: Path,
) -> CeqanetBundleArtifactVerification | None:
    """Verify one manifest artifact entry."""

    filename = _string_or_none(entry.get("filename"))
    artifact_type = _string_or_none(entry.get("artifact_type"))
    expected_sha256 = _string_or_none(entry.get("sha256"))
    expected_byte_count = _int_or_none(entry.get("byte_count"))
    if filename is None or artifact_type is None or expected_sha256 is None:
        return None
    if (
        filename in {".", ".."}
        or filename != Path(filename).name
        or "\\" in filename
        or "\x00" in filename
    ):
        raise ValueError("Bundle artifact filename must be a safe basename")
    if expected_byte_count is not None and expected_byte_count > _MAX_BUNDLE_ARTIFACT_BYTES:
        raise ValueError("Bundle artifact declared byte count exceeds limit")

    artifact_path = bundle_dir / filename
    _require_contained_bundle_file(artifact_path, root=root)
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

    digest = hashlib.sha256()
    actual_byte_count = 0
    with _open_regular_bundle_file(artifact_path) as artifact_file:
        while True:
            chunk = artifact_file.read(
                min(
                    _BUNDLE_READ_CHUNK_BYTES,
                    _MAX_BUNDLE_ARTIFACT_BYTES - actual_byte_count + 1,
                    remaining_bytes[0] + 1,
                )
            )
            if not chunk:
                break
            actual_byte_count += len(chunk)
            if actual_byte_count > _MAX_BUNDLE_ARTIFACT_BYTES:
                raise ValueError("Bundle artifact exceeds inspection byte limit")
            remaining_bytes[0] -= len(chunk)
            if remaining_bytes[0] < 0:
                raise ValueError("Bundle exceeds aggregate inspection byte limit")
            digest.update(chunk)
    actual_sha256 = digest.hexdigest()
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
