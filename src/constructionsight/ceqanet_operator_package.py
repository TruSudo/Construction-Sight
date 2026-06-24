"""CEQAnet operator package service.

This module combines a CEQAnet chain report, persistence preview, and write plan
into one deterministic non-mutating review artifact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from constructionsight.ceqanet_persistence_preview import build_ceqanet_persistence_preview
from constructionsight.ceqanet_write_plan import build_ceqanet_write_plan


@dataclass(frozen=True)
class CeqanetOperatorPackage:
    """Non-mutating operator-review package for a CEQAnet chain report."""

    chain_report: dict[str, Any]
    persistence_preview: dict[str, object]
    write_plan: dict[str, object]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe operator package payload."""

        chain_metadata = _metadata_object(self.chain_report, field_name="chain_report")
        preview_metadata = _metadata_object(
            self.persistence_preview,
            field_name="persistence_preview",
        )
        write_plan_metadata = _metadata_object(self.write_plan, field_name="write_plan")

        return {
            "metadata": {
                "schema_version": "ceqanet_operator_package.v1",
                "chain_schema_version": chain_metadata.get("schema_version"),
                "preview_schema_version": preview_metadata.get("schema_version"),
                "write_plan_schema_version": write_plan_metadata.get("schema_version"),
                "result_record_count": chain_metadata.get("result_record_count"),
                "ceqa_record_count": preview_metadata.get("ceqa_record_count"),
                "site_count": preview_metadata.get("site_count"),
                "entity_count": preview_metadata.get("entity_count"),
                "operation_count": write_plan_metadata.get("operation_count"),
                "skipped_record_count": preview_metadata.get("skipped_record_count"),
                "skipped_item_count": write_plan_metadata.get("skipped_item_count"),
                "warning_count": len(self.warnings),
                "network_executed": False,
                "database_opened": False,
                "persistence_mutated": False,
            },
            "chain_report": self.chain_report,
            "persistence_preview": self.persistence_preview,
            "write_plan": self.write_plan,
            "warnings": list(self.warnings),
        }


def build_ceqanet_operator_package(chain_report: dict[str, Any]) -> CeqanetOperatorPackage:
    """Build a CEQAnet operator package from one chain report."""

    _validate_chain_report(chain_report)
    persistence_preview = build_ceqanet_persistence_preview(chain_report).to_dict()
    write_plan = build_ceqanet_write_plan(cast(dict[str, Any], persistence_preview)).to_dict()
    warnings = _warnings_for_package(chain_report, persistence_preview, write_plan)

    return CeqanetOperatorPackage(
        chain_report=chain_report,
        persistence_preview=persistence_preview,
        write_plan=write_plan,
        warnings=tuple(warnings),
    )


def _validate_chain_report(chain_report: dict[str, Any]) -> None:
    """Validate top-level CEQAnet chain report shape."""

    metadata = chain_report.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Chain report must contain metadata.")
    schema_version = metadata.get("schema_version")
    if schema_version != "ceqanet_chain_report.v1":
        raise ValueError("Chain report schema_version must be ceqanet_chain_report.v1.")
    enrichment = chain_report.get("enrichment")
    if not isinstance(enrichment, dict):
        raise ValueError("Chain report must contain an enrichment object.")


def _warnings_for_package(
    chain_report: dict[str, Any],
    persistence_preview: dict[str, object],
    write_plan: dict[str, object],
) -> list[str]:
    """Return package-level review warnings."""

    warnings: list[str] = []
    chain_metadata = _metadata_object(chain_report, field_name="chain_report")
    preview_metadata = _metadata_object(persistence_preview, field_name="persistence_preview")
    write_plan_metadata = _metadata_object(write_plan, field_name="write_plan")

    if _int_value(chain_metadata.get("missing_detail_count")) > 0:
        warnings.append("Chain report contains result records missing detail-page enrichment.")
    if _int_value(chain_metadata.get("sch_mismatch_count")) > 0:
        warnings.append("Chain report contains SCH mismatch warnings.")
    if _int_value(preview_metadata.get("skipped_record_count")) > 0:
        warnings.append("Persistence preview skipped one or more enriched records.")
    if _int_value(write_plan_metadata.get("skipped_item_count")) > 0:
        warnings.append("Write plan skipped one or more preview items.")
    if _int_value(write_plan_metadata.get("operation_count")) == 0:
        warnings.append("Write plan contains no operations.")

    return warnings


def _metadata_object(
    payload: dict[str, Any] | dict[str, object],
    *,
    field_name: str,
) -> dict[str, object]:
    """Return the metadata object from a package component."""

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"{field_name} must contain metadata.")
    return cast(dict[str, object], metadata)


def _int_value(value: object) -> int:
    """Return integer values while treating missing/non-integers as zero."""

    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0
