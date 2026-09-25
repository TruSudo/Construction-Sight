"""Command-line external capability matrix and gap-report tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.external_intelligence_models import CapabilityDomain, ReferencePlatform
from constructionsight.external_intelligence_registry import (
    build_capability_gap_report,
    capability_matrix_rows,
    get_external_capabilities,
)
from constructionsight.storage.runtime_artifacts import write_runtime_text

app = typer.Typer(help="Inspect lawful Shovels/Regrid capability targets.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Inspect lawful Shovels/Regrid capability targets."""


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


def _domain_filter(value: str | None) -> CapabilityDomain | None:
    """Parse an optional capability-domain filter."""

    return CapabilityDomain(value) if value is not None else None


def _render_matrix(rows: list[dict[str, str]]) -> None:
    """Render compact capability matrix rows."""

    table = Table(title="External Intelligence Capability Matrix")
    table.add_column("Platform")
    table.add_column("Domain")
    table.add_column("Capability")
    table.add_column("Status")
    table.add_column("Boundary")
    for row in rows:
        table.add_row(
            row["platform"],
            row["domain"],
            row["label"],
            row["status"],
            row["lawful_boundary"],
        )
    console.print(table)


def _render_report(payload: dict[str, object]) -> None:
    """Render a compact gap report."""

    table = Table(title="External Capability Gap Report")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("report_id", str(payload["report_id"]))
    table.add_row("capabilities_reviewed", str(payload["capabilities_reviewed"]))
    table.add_row("gaps", str(len(cast(list[object], payload["gaps"]))))
    table.add_row(
        "outperform_targets",
        str(len(cast(list[object], payload["outperform_targets"]))),
    )
    table.add_row(
        "blocked_by_license",
        str(len(cast(list[object], payload["blocked_by_license"]))),
    )
    console.print(table)


@app.command("matrix")
def matrix(
    platform: Annotated[
        str | None,
        typer.Option("--platform", help="Optional platform filter: shovels or regrid."),
    ] = None,
    domain: Annotated[
        str | None,
        typer.Option("--domain", help="Optional capability-domain filter."),
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
    """Show lawful Shovels/Regrid capability targets."""

    _reject_output_without_json(output_path, json_output)
    capabilities = get_external_capabilities(
        platform=_platform_filter(platform),
        domain=_domain_filter(domain),
    )
    rows = capability_matrix_rows(capabilities)
    if output_path is not None:
        _write_json_file(output_path, rows)
        typer.echo(f"Wrote external capability matrix JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(rows, indent=2, sort_keys=True, default=str))
        return
    _render_matrix(rows)


@app.command("gap-report")
def gap_report(
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable gap-report JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write gap-report JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show capability gaps, blocked licensed targets, and outperform targets."""

    _reject_output_without_json(output_path, json_output)
    payload = build_capability_gap_report().to_dict()
    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote external capability gap report JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_report(payload)
