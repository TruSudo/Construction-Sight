"""Audit package CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.models import PublicSource
from constructionsight.source_verification_evidence_service import (
    build_authorized_source_verification_evidence_package,
    build_source_verification_evidence_package,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text

app = typer.Typer(help="ConstructionSight audit package tools.")
console = Console()


def _load_sources_from_json(path: Path) -> list[PublicSource]:
    data: Any = json.loads(read_runtime_text(path))
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
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help="Optional local audit identity; this is not authentication.",
        ),
    ] = None,
    authorization_reason: Annotated[
        str,
        typer.Option(
            "--authorization-reason",
            help="Reason for the exact bounded public reachability check.",
        ),
    ] = "Build one reviewed source-verification evidence package.",
) -> None:
    """Build a report-only package from source registry records."""

    sources = _load_sources_from_json(registry_path)
    adapter_specs = default_adapter_family_specs()
    try:
        package = (
            build_authorized_source_verification_evidence_package(
                sources,
                adapter_specs,
                caller_confirmation=True,
                authorization_reason=authorization_reason,
                operator_id=operator_id,
            )
            if check_http
            else build_source_verification_evidence_package(
                sources,
                adapter_specs,
                check_http=False,
            )
        )
    except (AuthorizationDeniedError, ValueError) as exc:
        typer.echo(f"Audit package build blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc
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
