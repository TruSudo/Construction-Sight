"""Source status report CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_status_report import build_source_status_report

app = typer.Typer(help="ConstructionSight source status reporting tools.")
console = Console()


def _load_sources_from_json(registry_path: Path) -> list[PublicSource]:
    """Load source records from a JSON registry file."""

    data: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Source registry JSON must be a list of source records.")
    return [PublicSource.model_validate(item) for item in data]


@app.callback()
def source_status_root() -> None:
    """ConstructionSight source status commands."""


@app.command("report")
def source_status_report(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    """Print source status rows from registry records and adapter specs."""

    sources = _load_sources_from_json(registry_path)
    report = build_source_status_report(sources, default_adapter_family_specs())
    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return
    summary = Table(title="ConstructionSight Source Status")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(report.source_count))
    summary.add_row("Verified usable sources", str(report.verified_source_count))
    for status_level, count in sorted(report.status_counts.items()):
        summary.add_row(status_level, str(count))
    console.print(summary)

    rows = Table(title="Source Status Rows")
    rows.add_column("Source")
    rows.add_column("Jurisdiction")
    rows.add_column("Platform")
    rows.add_column("Verification")
    rows.add_column("Adapter")
    rows.add_column("Status")
    rows.add_column("Verified use")
    rows.add_column("Reason")
    for row in report.rows:
        rows.add_row(
            row.source_name,
            row.jurisdiction_name,
            row.platform_family,
            row.verification_status,
            row.adapter_status,
            row.status_level,
            str(row.can_use_as_verified_source),
            row.reason,
        )
    console.print(rows)
