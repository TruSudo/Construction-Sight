"""CEQAnet operator bundle service.

This module writes a deterministic review bundle from an existing CEQAnet
operator package. It performs no network requests, database access, or
persistence mutation.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from constructionsight.ceqanet_operator_report import build_ceqanet_operator_report

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
    """Write a deterministic CEQAnet operator bundle to disk."""

    if output_dir.is_symlink():
        raise ValueError("CEQAnet bundle output must not be a symlinked directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_ceqanet_operator_report(operator_package).to_dict()
    persistence_preview = _object_field(operator_package, "persistence_preview")
    write_plan = _object_field(operator_package, "write_plan")

    artifacts: list[CeqanetBundleArtifact] = []
    artifacts.append(
        _write_json_artifact(
            output_dir / "operator-package.json",
            operator_package,
            artifact_type="operator_package_json",
        )
    )
    artifacts.append(
        _write_json_artifact(
            output_dir / "persistence-preview.json",
            persistence_preview,
            artifact_type="persistence_preview_json",
        )
    )
    artifacts.append(
        _write_json_artifact(
            output_dir / "write-plan.json",
            write_plan,
            artifact_type="write_plan_json",
        )
    )
    artifacts.append(
        _write_json_artifact(
            output_dir / "operator-report.json",
            report,
            artifact_type="operator_report_json",
        )
    )
    artifacts.append(
        _write_text_artifact(
            output_dir / "operator-report.md",
            str(report["markdown"]),
            artifact_type="operator_report_markdown",
        )
    )

    bundle = CeqanetOperatorBundle(output_dir=output_dir, artifacts=tuple(artifacts))
    manifest = bundle.to_dict()
    manifest_artifact = _write_json_artifact(
        output_dir / "manifest.json",
        manifest,
        artifact_type="bundle_manifest_json",
    )

    return CeqanetOperatorBundle(
        output_dir=output_dir,
        artifacts=(*bundle.artifacts, manifest_artifact),
    )


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

    text = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    return _write_text_artifact(path, text, artifact_type=artifact_type)


def _write_text_artifact(path: Path, text: str, *, artifact_type: str) -> CeqanetBundleArtifact:
    """Write text and return artifact metadata."""

    data = text.encode("utf-8")
    limit = (
        _MAX_BUNDLE_MANIFEST_BYTES
        if path.name == "manifest.json"
        else _MAX_BUNDLE_ARTIFACT_BYTES
    )
    if len(data) > limit:
        raise ValueError("CEQAnet bundle artifact exceeds the byte limit")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=".ceqanet-bundle-",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return CeqanetBundleArtifact(
        filename=path.name,
        artifact_type=artifact_type,
        byte_count=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
