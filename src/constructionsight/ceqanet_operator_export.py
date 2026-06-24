"""CEQAnet operator export service.

This module turns an existing CEQAnet chain report into a complete local operator
review bundle and immediately verifies the written bundle. It performs no
network requests, database access, or persistence mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from constructionsight.ceqanet_operator_bundle import build_ceqanet_operator_bundle
from constructionsight.ceqanet_operator_bundle_verify import verify_ceqanet_operator_bundle
from constructionsight.ceqanet_operator_package import build_ceqanet_operator_package


@dataclass(frozen=True)
class CeqanetOperatorExport:
    """Result from building and verifying a CEQAnet operator export bundle."""

    output_dir: Path
    operator_package: dict[str, object]
    bundle_manifest: dict[str, object]
    bundle_verification: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe operator export payload."""

        package_metadata = _metadata_object(self.operator_package, field_name="operator_package")
        bundle_metadata = _metadata_object(self.bundle_manifest, field_name="bundle_manifest")
        verification_metadata = _metadata_object(
            self.bundle_verification,
            field_name="bundle_verification",
        )

        return {
            "metadata": {
                "schema_version": "ceqanet_operator_export.v1",
                "output_dir": str(self.output_dir),
                "package_schema_version": package_metadata.get("schema_version"),
                "bundle_schema_version": bundle_metadata.get("schema_version"),
                "verification_schema_version": verification_metadata.get("schema_version"),
                "result_record_count": package_metadata.get("result_record_count"),
                "ceqa_record_count": package_metadata.get("ceqa_record_count"),
                "operation_count": package_metadata.get("operation_count"),
                "bundle_artifact_count": bundle_metadata.get("artifact_count"),
                "verified_artifact_count": verification_metadata.get("verified_count"),
                "missing_artifact_count": verification_metadata.get("missing_count"),
                "mismatched_artifact_count": verification_metadata.get("mismatch_count"),
                "malformed_artifact_count": verification_metadata.get("malformed_artifact_count"),
                "verification_passed": verification_metadata.get("passed"),
                "network_executed": False,
                "database_opened": False,
                "persistence_mutated": False,
            },
            "operator_package": self.operator_package,
            "bundle_manifest": self.bundle_manifest,
            "bundle_verification": self.bundle_verification,
        }


def build_ceqanet_operator_export(
    chain_report: dict[str, Any],
    *,
    output_dir: Path,
) -> CeqanetOperatorExport:
    """Build package, bundle, and bundle verification from one chain report."""

    operator_package = build_ceqanet_operator_package(chain_report).to_dict()
    bundle_manifest = build_ceqanet_operator_bundle(
        operator_package,
        output_dir=output_dir,
    ).to_dict()
    bundle_verification = verify_ceqanet_operator_bundle(bundle_dir=output_dir).to_dict()

    return CeqanetOperatorExport(
        output_dir=output_dir,
        operator_package=operator_package,
        bundle_manifest=bundle_manifest,
        bundle_verification=bundle_verification,
    )


def _metadata_object(payload: dict[str, object], *, field_name: str) -> dict[str, object]:
    """Return metadata object from an export component."""

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"{field_name} must contain metadata.")
    return metadata
