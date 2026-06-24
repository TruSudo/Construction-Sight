"""Command-line CEQAnet write plan preview.

This CLI reads an existing CEQAnet persistence preview JSON and emits a
deterministic write plan. It does not open databases or mutate persistence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_write_plan import build_ceqanet_write_plan

app = typer.Typer(help="Build CEQAnet write plan previews.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Build CEQAnet write plan previews."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_json_object(input_path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{input_path} is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _build_write_plan_payload(preview_payload: dict[str, Any]) -> dict[str, object]:
    """Build write plan payload and convert validation errors to CLI errors."""

    try:
        return build_ceqanet_write_plan(preview_payload).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _write_or_print_json(payload: dict[str, object], output_path: Path | None) -> None:
    """Write JSON to a file or print it to stdout."""

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet write plan JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact write plan summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    summary = Table(title="CEQAnet Write Plan Preview")
    summary.add_column("Field")
    summary.add_column("Value")
    for field_name in (
        "schema_version",
        "operation_count",
        "skipped_item_count",
        "action",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        summary.add_row(field_name, str(metadata.get(field_name)))
    console.print(summary)

    operations = cast(list[dict[str, object]], payload["operations"])
    if operations:
        table = Table(title="Planned Operations")
        table.add_column("Operation ID")
        table.add_column("Target")
        table.add_column("Key")
        for operation in operations:
            table.add_row(
                str(operation.get("operation_id") or ""),
                str(operation.get("target_collection") or ""),
                str(operation.get("target_key") or ""),
            )
        console.print(table)


@app.command("build")
def build_write_plan(
    persistence_preview_path: Annotated[
        Path,
        typer.Option(
            "--persistence-preview",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet persistence preview JSON.",
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
    """Build a non-mutating CEQAnet write plan preview."""

    _reject_output_without_json(output_path, json_output)
    preview_payload = _load_json_object(persistence_preview_path)
    payload = _build_write_plan_payload(preview_payload)
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {"persistence_preview_path": str(persistence_preview_path)}

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
