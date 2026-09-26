"""Command-line CEQAnet operator archive verifier.

This CLI verifies deterministic CEQAnet operator ZIP archives. It performs no
network requests, database access, or persistence mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_operator_archive_verify import verify_ceqanet_operator_archive
from constructionsight.storage.runtime_artifacts import write_runtime_text

app = typer.Typer(help="Verify deterministic CEQAnet operator ZIP archives.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Verify deterministic CEQAnet operator ZIP archives."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""
    write_runtime_text(
        output_path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


def _render_summary(payload: dict[str, object]) -> None:
    """Render compact archive verification summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    table = Table(title="CEQAnet Operator Archive Verification")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "schema_version",
        "zip_entry_count",
        "archived_file_count",
        "artifact_count",
        "verified_count",
        "missing_count",
        "mismatch_count",
        "malformed_artifact_count",
        "archive_issue_count",
        "duplicate_filename_count",
        "manifest_status",
        "passed",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        table.add_row(field_name, str(metadata.get(field_name)))
    console.print(table)

    artifacts = cast(list[dict[str, object]], payload["artifacts"])
    if artifacts:
        artifact_table = Table(title="Archive Artifact Verification")
        artifact_table.add_column("Filename")
        artifact_table.add_column("Type")
        artifact_table.add_column("Status")
        artifact_table.add_column("Bytes")
        artifact_table.add_column("Reason")
        for artifact in artifacts:
            artifact_table.add_row(
                str(artifact.get("filename") or ""),
                str(artifact.get("artifact_type") or ""),
                str(artifact.get("status") or ""),
                str(artifact.get("actual_byte_count") or ""),
                str(artifact.get("reason") or ""),
            )
        console.print(artifact_table)


@app.command("verify")
def verify_operator_archive(
    archive_path: Annotated[
        Path,
        typer.Option(
            "--archive",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="CEQAnet operator ZIP archive to verify.",
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
    """Verify a deterministic CEQAnet operator ZIP archive."""

    _reject_output_without_json(output_path, json_output)
    try:
        payload = verify_ceqanet_operator_archive(archive_path=archive_path).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet operator archive verification JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_summary(payload)
