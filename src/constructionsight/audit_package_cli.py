"""Audit package CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_verification_evidence_service import (
    build_source_verification_evidence_package,
)

app = typer.Typer(help="ConstructionSight audit package tools.")
console = Console()


def _load_sources_from_json(path: Path) -> list[PublicSource]:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Registry JSON must be a list.")
    return [PublicSource.model_validate(item) for item in data]


@app.callback()
def audit_package_root() -> None:
    """ConstructionSight audit package commands."""


@app.command("build")
def build_audit_package(
    registry_path: Annotated[Path, typer.Argument(help="Path to source registry JSON.")],
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
    check_http: Annotated[bool, typer.Option("--check-http")] = False,
) -> None:
    """Build a report-only package from source registry records."""

    package = build_source_verification_evidence_package(
        _load_sources_from_json(registry_path),
        default_adapter_family_specs(),
        check_http=check_http,
    )
    if json_output:
        console.print_json(json.dumps(package.to_dict()))
        return

    summary = Table(title="ConstructionSight Audit Package")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(package.source_count))
    for recommendation, count in sorted(package.recommendation_counts.items()):
        summary.add_row(recommendation, str(count))
    console.print(summary)

    rows = Table(title="Audit Package Rows")
    rows.add_column("Source")
    rows.add_column("State")
    rows.add_column("Redirect")
    rows.add_column("HTTP")
    rows.add_column("Recommendation")
    for row in package.rows:
        http_status = "not_checked"
        if row.http_checked:
            http_status = str(row.http_status_code or "error")
        rows.add_row(
            row.source_name,
            row.readiness_status,
            row.redirect_classification.value,
            http_status,
            row.recommendation.value,
        )
    console.print(rows)
