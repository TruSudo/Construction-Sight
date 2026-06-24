"""CEQAnet operator report service.

This module converts a CEQAnet operator package into a deterministic Markdown
review report. It performs no network requests, database access, or persistence
mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True)
class CeqanetOperatorReport:
    """Markdown report derived from one CEQAnet operator package."""

    markdown: str
    metadata: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe report payload."""

        return {
            "metadata": self.metadata,
            "markdown": self.markdown,
        }


def build_ceqanet_operator_report(operator_package: dict[str, Any]) -> CeqanetOperatorReport:
    """Build a deterministic Markdown report from a CEQAnet operator package."""

    _validate_operator_package(operator_package)
    package_metadata = _metadata_object(operator_package, field_name="operator_package")
    persistence_preview = _object_field(operator_package, "persistence_preview")
    write_plan = _object_field(operator_package, "write_plan")
    warnings = _string_list(operator_package.get("warnings"))

    ceqa_records = _object_list(persistence_preview.get("ceqa_records"))
    operations = _object_list(write_plan.get("operations"))

    markdown = "\n".join(
        [
            "# CEQAnet Operator Report",
            "",
            "## Summary",
            _summary_table(package_metadata),
            "",
            "## Review Warnings",
            _warnings_section(warnings),
            "",
            "## CEQA Record Preview",
            _ceqa_record_table(ceqa_records),
            "",
            "## Planned Operations",
            _operation_table(operations),
            "",
            "## Execution Boundary",
            _boundary_section(package_metadata),
            "",
        ]
    )

    return CeqanetOperatorReport(
        markdown=markdown,
        metadata={
            "schema_version": "ceqanet_operator_report.v1",
            "package_schema_version": package_metadata.get("schema_version"),
            "ceqa_record_count": package_metadata.get("ceqa_record_count"),
            "operation_count": package_metadata.get("operation_count"),
            "warning_count": len(warnings),
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
    )


def _validate_operator_package(operator_package: dict[str, Any]) -> None:
    """Validate top-level operator package shape."""

    metadata = _metadata_object(operator_package, field_name="operator_package")
    schema_version = metadata.get("schema_version")
    if schema_version != "ceqanet_operator_package.v1":
        raise ValueError(
            "Operator package schema_version must be ceqanet_operator_package.v1."
        )
    _object_field(operator_package, "persistence_preview")
    _object_field(operator_package, "write_plan")


def _summary_table(metadata: dict[str, object]) -> str:
    """Return Markdown summary table."""

    rows = [
        ("Result records", metadata.get("result_record_count")),
        ("CEQA records", metadata.get("ceqa_record_count")),
        ("Sites", metadata.get("site_count")),
        ("Entities", metadata.get("entity_count")),
        ("Operations", metadata.get("operation_count")),
        ("Warnings", metadata.get("warning_count")),
    ]
    return _markdown_table(("Metric", "Value"), rows)


def _warnings_section(warnings: list[str]) -> str:
    """Return Markdown warning section."""

    if not warnings:
        return "No package-level warnings."
    return "\n".join(f"- {warning}" for warning in warnings)


def _ceqa_record_table(records: list[dict[str, object]]) -> str:
    """Return Markdown table for CEQA record previews."""

    if not records:
        return "No CEQA record previews."
    rows = []
    for record in records:
        rows.append(
            (
                record.get("ceqa_key"),
                record.get("title"),
                record.get("state_clearinghouse_number"),
                record.get("county"),
                record.get("lead_agency"),
            )
        )
    return _markdown_table(("Key", "Title", "SCH", "County", "Lead Agency"), rows)


def _operation_table(operations: list[dict[str, object]]) -> str:
    """Return Markdown table for planned operations."""

    if not operations:
        return "No planned operations."
    rows = []
    for operation in operations:
        rows.append(
            (
                operation.get("operation_id"),
                operation.get("action"),
                operation.get("target_collection"),
                operation.get("target_key"),
            )
        )
    return _markdown_table(("Operation ID", "Action", "Target", "Key"), rows)


def _boundary_section(metadata: dict[str, object]) -> str:
    """Return Markdown execution-boundary section."""

    rows = [
        ("Network executed", metadata.get("network_executed")),
        ("Database opened", metadata.get("database_opened")),
        ("Persistence mutated", metadata.get("persistence_mutated")),
    ]
    return _markdown_table(("Boundary", "Value"), rows)


def _markdown_table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    """Return a GitHub-flavored Markdown table."""

    header_row = _markdown_row(headers)
    divider_row = _markdown_row(tuple("---" for _ in headers))
    body_rows = [_markdown_row(row) for row in rows]
    return "\n".join([header_row, divider_row, *body_rows])


def _markdown_row(values: tuple[object, ...]) -> str:
    """Return one Markdown table row."""

    return "| " + " | ".join(_escape_markdown_cell(value) for value in values) + " |"


def _metadata_object(payload: dict[str, Any], *, field_name: str) -> dict[str, object]:
    """Return metadata object from a payload."""

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"{field_name} must contain metadata.")
    return cast(dict[str, object], metadata)


def _object_field(payload: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Return an object field from a payload."""

    value = payload.get(field_name)
    if not isinstance(value, dict):
        raise ValueError(f"Operator package must contain {field_name} object.")
    return cast(dict[str, Any], value)


def _object_list(value: object) -> list[dict[str, object]]:
    """Return list of JSON objects while ignoring malformed list items."""

    if not isinstance(value, list):
        return []
    objects: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, dict):
            objects.append(cast(dict[str, object], item))
    return objects


def _string_list(value: object) -> list[str]:
    """Return list of string values while ignoring malformed list items."""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _escape_markdown_cell(value: object) -> str:
    """Escape Markdown table cell delimiters."""

    if value is None:
        return ""
    text = str(value).replace("\n", " ").strip()
    return text.replace("|", "\\|")
