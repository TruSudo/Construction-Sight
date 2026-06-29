"""Command-line parcel source registry tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.parcel_source_models import ParcelProviderKind
from constructionsight.parcel_source_registry import (
    build_parcel_source_report,
    get_parcel_sources,
    parcel_source_matrix_rows,
)

app = typer.Typer(help="Inspect parcel source targets and readiness.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Inspect parcel source targets and readiness."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _write_json_file(output_path: Path, payload: object) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _provider_filter(value: str | None) -> ParcelProviderKind | None:
    """Parse an optional provider-kind filter."""

    return ParcelProviderKind(value) if value is not None else None


def _render_matrix(rows: list[dict[str, str]]) -> None:
    """Render compact source matrix rows."""

    table = Table(title="Parcel Source Registry")
    table.add_column("County")
    table.add_column("Source")
    table.add_column("Provider")
    table.add_column("Status")
    table.add_column("Geometry")
    table.add_column("Priority")
    for row in rows:
        table.add_row(
            row["county"],
            row["source_name"],
            row["provider_kind"],
            row["coverage_status"],
            row["geometry_support"],
            row["priority"],
        )
    console.print(table)


def _render_report(payload: dict[str, object]) -> None:
    """Render a compact registry report."""

    table = Table(title="Parcel Source Registry Report")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("report_id", str(payload["report_id"]))
    table.add_row("sources_reviewed", str(payload["sources_reviewed"]))
    table.add_row("counties", ", ".join(cast(list[str], payload["counties"])))
    table.add_row("ready_sources", str(len(cast(list[object], payload["ready_sources"]))))
    table.add_row("target_sources", str(len(cast(list[object], payload["target_sources"]))))
    table.add_row(
        "blocked_sources",
        str(len(cast(list[object], payload["blocked_sources"]))),
    )
    console.print(table)


@app.command("matrix")
def matrix(
    county: Annotated[
        str | None,
        typer.Option("--county", help="Optional county filter."),
    ] = None,
    provider_kind: Annotated[
        str | None,
        typer.Option("--provider-kind", help="Optional provider-kind filter."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable matrix JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write matrix JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show parcel source targets."""

    _reject_output_without_json(output_path, json_output)
    sources = get_parcel_sources(
        county=county,
        provider_kind=_provider_filter(provider_kind),
    )
    rows = parcel_source_matrix_rows(sources)
    if output_path is not None:
        _write_json_file(output_path, rows)
        typer.echo(f"Wrote parcel source matrix JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(rows, indent=2, sort_keys=True, default=str))
        return
    _render_matrix(rows)


@app.command("report")
def report(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable report JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write report JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show parcel source readiness report."""

    _reject_output_without_json(output_path, json_output)
    payload = build_parcel_source_report().to_dict()
    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote parcel source registry report JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_report(payload)
