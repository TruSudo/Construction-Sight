"""Command-line CEQAnet operator bundle builder.

This CLI reads an existing CEQAnet operator package JSON and writes a deterministic
review bundle. It performs no network requests, database access, or persistence
mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_operator_bundle import build_ceqanet_operator_bundle
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="Build CEQAnet operator review bundles.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Build CEQAnet operator review bundles."""


def _load_json_object(input_path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        payload = json.loads(read_runtime_text(input_path))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{input_path} is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""
    write_runtime_text(
        output_path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact bundle summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    table = Table(title="CEQAnet Operator Bundle")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "schema_version",
        "artifact_count",
        "output_dir",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        table.add_row(field_name, str(metadata.get(field_name)))
    console.print(table)

    artifacts = cast(list[dict[str, object]], payload["artifacts"])
    artifact_table = Table(title="Bundle Artifacts")
    artifact_table.add_column("Filename")
    artifact_table.add_column("Type")
    artifact_table.add_column("Bytes")
    for artifact in artifacts:
        artifact_table.add_row(
            str(artifact.get("filename") or ""),
            str(artifact.get("artifact_type") or ""),
            str(artifact.get("byte_count") or ""),
        )
    console.print(artifact_table)


@app.command("build")
def build_operator_bundle(
    operator_package_path: Annotated[
        Path,
        typer.Option(
            "--operator-package",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet operator package JSON.",
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            help="Directory where bundle artifacts will be written.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable manifest JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write manifest JSON to a separate file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Build a deterministic CEQAnet operator review bundle."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)

    operator_package = _load_json_object(operator_package_path)
    try:
        payload = build_ceqanet_operator_bundle(
            operator_package,
            output_dir=output_dir,
        ).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {"operator_package_path": str(operator_package_path)}

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet operator bundle manifest JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_summary(payload)
