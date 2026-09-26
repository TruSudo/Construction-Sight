"""CEQAnet operator bundle service.

This module writes a deterministic review bundle from an existing CEQAnet
operator package. It performs no network requests, database access, or
persistence mutation.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, cast

from constructionsight.ceqanet_operator_bundle_verify import (
    verify_ceqanet_operator_bundle,
)
from constructionsight.ceqanet_operator_report import build_ceqanet_operator_report
from constructionsight.storage.runtime_artifacts import (
    RuntimeArtifactError,
    anchored_artifact_parent,
    open_runtime_artifact,
    publish_runtime_artifact,
)

_MAX_BUNDLE_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_BUNDLE_MANIFEST_BYTES = 1024 * 1024


@dataclass(frozen=True)
class CeqanetBundleArtifact:
    """One file in a CEQAnet operator bundle."""

    filename: str
    artifact_type: str
    byte_count: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe artifact metadata."""

        return {
            "filename": self.filename,
            "artifact_type": self.artifact_type,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class CeqanetOperatorBundle:
    """Result from writing a CEQAnet operator bundle."""

    output_dir: Path
    artifacts: tuple[CeqanetBundleArtifact, ...]

    @property
    def artifact_count(self) -> int:
        """Return written artifact count."""

        return len(self.artifacts)

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe bundle manifest."""

        return {
            "metadata": {
                "schema_version": "ceqanet_operator_bundle.v1",
                "artifact_count": self.artifact_count,
                "output_dir": str(self.output_dir),
                "network_executed": False,
                "database_opened": False,
                "persistence_mutated": False,
            },
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }


def build_ceqanet_operator_bundle(
    operator_package: dict[str, Any],
    *,
    output_dir: Path,
) -> CeqanetOperatorBundle:
    """Stage a complete bundle, then publish payloads before the success manifest."""

    if output_dir.is_symlink():
        raise ValueError("CEQAnet bundle output must not be a symlinked directory")
    report = build_ceqanet_operator_report(operator_package).to_dict()
    persistence_preview = _object_field(operator_package, "persistence_preview")
    write_plan = _object_field(operator_package, "write_plan")

    # Materialize and durably validate every coupled output before touching a
    # previously valid bundle. The final manifest is a success marker and is
    # never present while a mixed-generation payload set is being published.
    with tempfile.TemporaryDirectory(prefix="constructionsight-bundle-stage-") as stage_name:
        stage_dir = Path(stage_name)
        artifacts: list[CeqanetBundleArtifact] = []
        artifacts.append(
            _write_json_artifact(
                stage_dir / "operator-package.json",
                operator_package,
                artifact_type="operator_package_json",
            )
        )
        artifacts.append(
            _write_json_artifact(
                stage_dir / "persistence-preview.json",
                persistence_preview,
                artifact_type="persistence_preview_json",
            )
        )
        artifacts.append(
            _write_json_artifact(
                stage_dir / "write-plan.json",
                write_plan,
                artifact_type="write_plan_json",
            )
        )
        artifacts.append(
            _write_json_artifact(
                stage_dir / "operator-report.json",
                report,
                artifact_type="operator_report_json",
            )
        )
        artifacts.append(
            _write_text_artifact(
                stage_dir / "operator-report.md",
                str(report["markdown"]),
                artifact_type="operator_report_markdown",
            )
        )

        payload_bundle = CeqanetOperatorBundle(
            output_dir=output_dir,
            artifacts=tuple(artifacts),
        )
        manifest_artifact = _write_json_artifact(
            stage_dir / "manifest.json",
            payload_bundle.to_dict(),
            artifact_type="bundle_manifest_json",
        )
        staged_verification = verify_ceqanet_operator_bundle(bundle_dir=stage_dir)
        if not staged_verification.passed:
            raise RuntimeArtifactError(
                "staged CEQAnet bundle did not pass complete verification"
            )

        with _serialized_bundle_output(output_dir) as parent:
            _invalidate_bundle_manifest(parent)
            for artifact in artifacts:
                _publish_staged_artifact(
                    stage_dir / artifact.filename,
                    output_dir / artifact.filename,
                    artifact=artifact,
                    parent=parent,
                )
            # Publish success evidence only after every authoritative payload is
            # durable and content-verified in the final directory.
            _publish_staged_artifact(
                stage_dir / "manifest.json",
                output_dir / "manifest.json",
                artifact=manifest_artifact,
                parent=parent,
            )
            _clear_pending_bundle_manifest(parent)

    return CeqanetOperatorBundle(
        output_dir=output_dir,
        artifacts=(*payload_bundle.artifacts, manifest_artifact),
    )


_BUNDLE_LOCK_NAME = ".ceqanet-bundle.lock"
_BUNDLE_PENDING_MANIFEST = ".ceqanet-bundle.pending-manifest.json"


@contextmanager
def _serialized_bundle_output(output_dir: Path) -> Iterator[int]:
    """Pin and exclusively lock one bundle directory for the entire commit."""

    if os.name != "posix":
        raise RuntimeArtifactError("native bundle transaction locking is unavailable")
    import fcntl

    lock_path = output_dir / _BUNDLE_LOCK_NAME
    with anchored_artifact_parent(lock_path, create_parents=True) as (parent, lock_name):
        directory = os.fstat(parent)
        if directory.st_uid != os.geteuid() or stat.S_IMODE(directory.st_mode) & 0o022:
            raise RuntimeArtifactError(
                "bundle transaction directory must be owned and not group/world writable"
            )
        descriptor = os.open(
            lock_name,
            os.O_RDWR
            | os.O_CREAT
            | os.O_NOFOLLOW
            | os.O_NONBLOCK
            | getattr(os, "O_CLOEXEC", 0),
            0o600,
            dir_fd=parent,
        )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            _require_lock_integrity(parent, lock_name, descriptor)
            os.fsync(parent)
            yield parent
            _require_lock_integrity(parent, lock_name, descriptor)
            os.fsync(parent)
        finally:
            os.close(descriptor)


def _require_lock_integrity(parent: int, name: str, descriptor: int) -> None:
    current = os.stat(name, dir_fd=parent, follow_symlinks=False)
    opened = os.fstat(descriptor)
    if (
        not stat.S_ISREG(current.st_mode)
        or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
        or current.st_uid != os.geteuid()
        or current.st_nlink != 1
        or stat.S_IMODE(current.st_mode) != 0o600
    ):
        raise RuntimeArtifactError("bundle transaction lock was replaced or altered")


def _invalidate_bundle_manifest(parent: int) -> None:
    """Retain any old manifest under a non-success name before payload mutation."""

    pending_exists = _regular_entry_exists(parent, _BUNDLE_PENDING_MANIFEST)
    manifest_exists = _regular_entry_exists(parent, "manifest.json")
    if manifest_exists and not pending_exists:
        os.link(
            "manifest.json",
            _BUNDLE_PENDING_MANIFEST,
            src_dir_fd=parent,
            dst_dir_fd=parent,
            follow_symlinks=False,
        )
        os.fsync(parent)
        pending_exists = True
    if manifest_exists:
        os.unlink("manifest.json", dir_fd=parent)
        os.fsync(parent)
    if pending_exists:
        _regular_entry_exists(parent, _BUNDLE_PENDING_MANIFEST, required=True)


def _clear_pending_bundle_manifest(parent: int) -> None:
    """Remove the recovery marker only after the new success manifest is durable."""

    if not _regular_entry_exists(parent, _BUNDLE_PENDING_MANIFEST):
        return
    os.unlink(_BUNDLE_PENDING_MANIFEST, dir_fd=parent)
    os.fsync(parent)


def _regular_entry_exists(parent: int, name: str, *, required: bool = False) -> bool:
    try:
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        if required:
            raise RuntimeArtifactError(
                f"required bundle transaction entry is absent: {name}"
            ) from None
        return False
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeArtifactError("bundle transaction entries must be regular files")
    return True


def _publish_staged_artifact(
    staged_path: Path,
    output_path: Path,
    *,
    artifact: CeqanetBundleArtifact,
    parent: int,
) -> None:
    """Publish one staged artifact and prove the exact staged bytes were committed."""

    limit = (
        _MAX_BUNDLE_MANIFEST_BYTES
        if artifact.filename == "manifest.json"
        else _MAX_BUNDLE_ARTIFACT_BYTES
    )
    observed_count = 0
    observed_digest = hashlib.sha256()
    with open_runtime_artifact(staged_path) as stream:
        def chunks() -> Iterator[bytes]:
            nonlocal observed_count
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                observed_count += len(chunk)
                if observed_count > limit:
                    raise RuntimeArtifactError("staged bundle artifact exceeds byte limit")
                observed_digest.update(chunk)
                yield chunk

        publish_runtime_artifact(
            output_path,
            chunks(),
            max_bytes=limit,
            replace_existing=True,
            parent=parent,
        )
    if (
        observed_count != artifact.byte_count
        or observed_digest.hexdigest() != artifact.sha256
    ):
        raise RuntimeArtifactError("staged bundle artifact identity changed before commit")

    committed_count = 0
    committed_digest = hashlib.sha256()
    with open_runtime_artifact(output_path, durable=True, parent=parent) as committed:
        while True:
            chunk = committed.read(64 * 1024)
            if not chunk:
                break
            committed_count += len(chunk)
            if committed_count > limit:
                raise RuntimeArtifactError("committed bundle artifact exceeds byte limit")
            committed_digest.update(chunk)
    if (
        committed_count != artifact.byte_count
        or committed_digest.hexdigest() != artifact.sha256
    ):
        raise RuntimeArtifactError("committed bundle artifact disagrees with staged identity")


def _object_field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Return an object field from an operator package."""

    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"Operator package must contain {field_name} object.")
    return cast(dict[str, Any], value)


def _write_json_artifact(
    path: Path,
    payload: dict[str, Any],
    *,
    artifact_type: str,
) -> CeqanetBundleArtifact:
    """Write deterministic JSON and return artifact metadata."""

    encoder = json.JSONEncoder(indent=2, sort_keys=True, default=str)
    return _write_serialized_artifact(
        path, chain(encoder.iterencode(payload), ("\n",)), artifact_type=artifact_type
    )


def _write_text_artifact(path: Path, text: str, *, artifact_type: str) -> CeqanetBundleArtifact:
    """Write text with the same bounded publication and digest contract as JSON."""

    return _write_serialized_artifact(path, (text,), artifact_type=artifact_type)


def _write_serialized_artifact(
    path: Path, fragments: Iterable[str], *, artifact_type: str
) -> CeqanetBundleArtifact:
    """Incrementally serialize, hash, and publish one bounded output artifact."""

    limit = (
        _MAX_BUNDLE_MANIFEST_BYTES
        if path.name == "manifest.json"
        else _MAX_BUNDLE_ARTIFACT_BYTES
    )
    byte_count = 0
    digest = hashlib.sha256()

    def chunks() -> Iterator[bytes]:
        nonlocal byte_count
        for fragment in fragments:
            for index in range(0, len(fragment), 16_384):
                chunk = fragment[index:index + 16_384].encode("utf-8")
                if byte_count + len(chunk) > limit:
                    raise ValueError("CEQAnet bundle artifact exceeds the byte limit")
                digest.update(chunk)
                byte_count += len(chunk)
                yield chunk

    publish_runtime_artifact(path, chunks(), max_bytes=limit, replace_existing=True)
    return CeqanetBundleArtifact(
        filename=path.name,
        artifact_type=artifact_type,
        byte_count=byte_count,
        sha256=digest.hexdigest(),
    )
