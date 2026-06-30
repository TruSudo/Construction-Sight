"""Source readiness workflow CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_readiness_service import build_source_readiness_report

app = typer.Typer(help="ConstructionSight source-readiness tools.")
console = Console()


def _load_sources_from_json(registry_path: Path) -> list[PublicSource]:
    """Load source records from a JSON registry file."""

    data: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Source registry JSON must be a list of source records.")
    return [PublicSource.model_validate(item) for item in data]


@app.callback()
def source_readiness_root() -> None:
    """ConstructionSight source-readiness commands."""


@app.command("check")
def source_readiness_check(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
    check_http: Annotated[
        bool,
        typer.Option("--check-http", help="Perform lightweight public HTTP checks."),
    ] = False,
) -> None:
    """Build a conservative source-readiness report without registry mutation."""

    sources = _load_sources_from_json(registry_path)
    report = build_source_readiness_report(
        sources,
        default_adapter_family_specs(),
        check_http=check_http,
    )
    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return
    summary = Table(title="ConstructionSight Source Readiness")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(report.source_count))
    for status, count in sorted(report.status_counts.items()):
        summary.add_row(status, str(count))
    console.print(summary)

    rows = Table(title="Source Readiness Rows")
    rows.add_column("Source")
    rows.add_column("Platform")
    rows.add_column("Verification")
    rows.add_column("Adapter")
    rows.add_column("Readiness")
    rows.add_column("HTTP")
    rows.add_column("Next action")
    for row in report.rows:
        http_status = "not_checked"
        if row.http_reachability.checked:
            http_status = str(row.http_reachability.status_code or row.http_reachability.error)
        rows.add_row(
            row.source_name,
            row.platform_family,
            row.verification_status,
            row.adapter_status,
            row.readiness_status.value,
            http_status,
            row.next_action,
        )
    console.print(rows)
