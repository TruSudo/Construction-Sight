"""Command-line CEQAnet operator package builder.

This CLI reads an existing CEQAnet chain report JSON and emits one deterministic
non-mutating package containing persistence preview and write-plan artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_operator_package import build_ceqanet_operator_package
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="Build CEQAnet operator review packages.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Build CEQAnet operator review packages."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_json_object(input_path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        payload = json.loads(read_runtime_text(input_path))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{input_path} is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _build_package_payload(chain_report: dict[str, Any]) -> dict[str, object]:
    """Build package payload and convert validation errors to CLI errors."""

    try:
        return build_ceqanet_operator_package(chain_report).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""
    write_runtime_text(
        output_path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


def _write_or_print_json(payload: dict[str, object], output_path: Path | None) -> None:
    """Write JSON to a file or print it to stdout."""

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet operator package JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact operator package summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    table = Table(title="CEQAnet Operator Package")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "schema_version",
        "result_record_count",
        "ceqa_record_count",
        "site_count",
        "entity_count",
        "operation_count",
        "warning_count",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        table.add_row(field_name, str(metadata.get(field_name)))
    console.print(table)


@app.command("build")
def build_operator_package(
    chain_report_path: Annotated[
        Path,
        typer.Option(
            "--chain-report",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet chain report JSON.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Build a non-mutating CEQAnet operator-review package."""

    _reject_output_without_json(output_path, json_output)
    chain_report = _load_json_object(chain_report_path)
    payload = _build_package_payload(chain_report)
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {"chain_report_path": str(chain_report_path)}

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
