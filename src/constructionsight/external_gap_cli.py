"""Command-line Shovels/Regrid research-gap alignment tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.external_gap_models import GapPriority
from constructionsight.external_gap_registry import (
    build_gap_alignment_report,
    gap_matrix_rows,
    get_knowledge_gaps,
    roadmap_rows,
)
from constructionsight.external_intelligence_models import ReferencePlatform
from constructionsight.storage.runtime_artifacts import write_runtime_text

app = typer.Typer(help="Inspect Shovels/Regrid research gaps and roadmap alignment.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Inspect Shovels/Regrid research gaps and roadmap alignment."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _write_json_file(output_path: Path, payload: object) -> None:
    """Write deterministic UTF-8 JSON output."""
    write_runtime_text(
        output_path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


def _platform_filter(value: str | None) -> ReferencePlatform | None:
    """Parse an optional platform filter."""

    return ReferencePlatform(value) if value is not None else None


def _priority_filter(value: str | None) -> GapPriority | None:
    """Parse an optional priority filter."""

    return GapPriority(value) if value is not None else None


def _render_gap_matrix(rows: list[dict[str, str]]) -> None:
    """Render a compact knowledge-gap table."""

    table = Table(title="Shovels/Regrid Knowledge Gaps")
    table.add_column("Priority")
    table.add_column("Platform")
    table.add_column("Capability")
    table.add_column("Suggested PR")
    table.add_column("Dependency")
    for row in rows:
        table.add_row(
            row["priority"],
            row["platform"],
            row["capability"],
            row["suggested_pr"],
            row["dependency"],
        )
    console.print(table)


def _render_roadmap(rows: list[dict[str, str]]) -> None:
    """Render a compact implementation roadmap."""

    table = Table(title="Shovels/Regrid Alignment Roadmap")
    table.add_column("Seq")
    table.add_column("Step")
    table.add_column("Risk")
    table.add_column("Goal")
    for row in rows:
        table.add_row(
            row["sequence"],
            row["title"],
            row["risk"],
            row["goal"],
        )
    console.print(table)


def _render_report(payload: dict[str, object]) -> None:
    """Render a compact alignment report."""

    table = Table(title="Shovels/Regrid Gap Alignment Report")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("report_id", str(payload["report_id"]))
    table.add_row("findings_reviewed", str(payload["findings_reviewed"]))
    table.add_row("gaps_reviewed", str(payload["gaps_reviewed"]))
    table.add_row("roadmap_steps", str(payload["roadmap_steps"]))
    table.add_row("critical_gaps", str(len(cast(list[object], payload["critical_gaps"]))))
    table.add_row("high_gaps", str(len(cast(list[object], payload["high_gaps"]))))
    console.print(table)


@app.command("gaps")
def gaps(
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="Optional platform filter."),
    ] = None,
    priority: Annotated[
        str | None,
        typer.Option("--priority", help="Optional priority filter."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable gap matrix JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write gap matrix JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show prioritized Shovels/Regrid knowledge gaps."""

    _reject_output_without_json(output_path, json_output)
    rows = gap_matrix_rows(
        get_knowledge_gaps(
            platform=_platform_filter(platform),
            priority=_priority_filter(priority),
        )
    )
    if output_path is not None:
        _write_json_file(output_path, rows)
        typer.echo(f"Wrote Shovels/Regrid gap matrix JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(rows, indent=2, sort_keys=True, default=str))
        return
    _render_gap_matrix(rows)


@app.command("roadmap")
def roadmap(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable roadmap JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write roadmap JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show the next implementation sequence."""

    _reject_output_without_json(output_path, json_output)
    rows = roadmap_rows()
    if output_path is not None:
        _write_json_file(output_path, rows)
        typer.echo(f"Wrote Shovels/Regrid roadmap JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(rows, indent=2, sort_keys=True, default=str))
        return
    _render_roadmap(rows)


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
    """Show the Shovels/Regrid alignment report."""

    _reject_output_without_json(output_path, json_output)
    payload = build_gap_alignment_report().to_dict()
    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote Shovels/Regrid alignment report JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_report(payload)
