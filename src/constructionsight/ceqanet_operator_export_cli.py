"""Command-line CEQAnet operator export builder.

This CLI reads an existing CEQAnet chain report JSON, writes a complete operator
review bundle, and verifies that bundle. It performs no network requests,
database access, or persistence mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_operator_export import build_ceqanet_operator_export

app = typer.Typer(help="Build and verify CEQAnet operator exports.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Build and verify CEQAnet operator exports."""


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


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact operator export summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    table = Table(title="CEQAnet Operator Export")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "schema_version",
        "output_dir",
        "ceqa_record_count",
        "operation_count",
        "bundle_artifact_count",
        "verified_artifact_count",
        "verification_passed",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        table.add_row(field_name, str(metadata.get(field_name)))
    console.print(table)


@app.command("build")
def build_operator_export(
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
    output_dir: Annotated[
        Path,
        typer.Option("--output-dir", help="Directory where export bundle will be written."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable export JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write export JSON to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Build a complete non-mutating CEQAnet operator export."""

    _reject_output_without_json(output_path, json_output)
    chain_report = _load_json_object(chain_report_path)
    try:
        payload = build_ceqanet_operator_export(
            chain_report,
            output_dir=output_dir,
        ).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {"chain_report_path": str(chain_report_path)}

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet operator export JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_summary(payload)
