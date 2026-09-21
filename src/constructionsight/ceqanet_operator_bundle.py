"""CEQAnet operator bundle service.

This module writes a deterministic review bundle from an existing CEQAnet
operator package. It performs no network requests, database access, or
persistence mutation.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Any, cast

from constructionsight.ceqanet_operator_report import build_ceqanet_operator_report
from constructionsight.storage.runtime_artifacts import publish_runtime_artifact

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
