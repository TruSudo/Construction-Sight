"""Command-line CEQAnet operator bundle verifier.

This CLI verifies a CEQAnet operator bundle manifest against local files. It
performs no network requests, database access, or persistence mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_operator_bundle_verify import verify_ceqanet_operator_bundle

app = typer.Typer(help="Verify CEQAnet operator review bundles.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Verify CEQAnet operator review bundles."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _render_summary(payload: dict[str, object]) -> None:
    """Render compact verification summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    table = Table(title="CEQAnet Operator Bundle Verification")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "schema_version",
        "artifact_count",
        "verified_count",
        "missing_count",
        "mismatch_count",
        "malformed_artifact_count",
        "passed",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        table.add_row(field_name, str(metadata.get(field_name)))
    console.print(table)

    artifacts = cast(list[dict[str, object]], payload["artifacts"])
    if artifacts:
        artifact_table = Table(title="Artifact Verification")
        artifact_table.add_column("Filename")
        artifact_table.add_column("Type")
        artifact_table.add_column("Status")
        artifact_table.add_column("Bytes")
        for artifact in artifacts:
            artifact_table.add_row(
                str(artifact.get("filename") or ""),
                str(artifact.get("artifact_type") or ""),
                str(artifact.get("status") or ""),
                str(artifact.get("actual_byte_count") or ""),
            )
        console.print(artifact_table)


@app.command("verify")
def verify_operator_bundle(
    bundle_dir: Annotated[
        Path,
        typer.Option(
            "--bundle-dir",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Directory containing CEQAnet operator bundle artifacts.",
        ),
    ],
    manifest_path: Annotated[
        Path | None,
        typer.Option(
            "--manifest",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Optional manifest path. Defaults to BUNDLE_DIR/manifest.json.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Verify a CEQAnet operator bundle manifest against local files."""

    _reject_output_without_json(output_path, json_output)
    try:
        payload = verify_ceqanet_operator_bundle(
            bundle_dir=bundle_dir,
            manifest_path=manifest_path,
        ).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet operator bundle verification JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_summary(payload)
