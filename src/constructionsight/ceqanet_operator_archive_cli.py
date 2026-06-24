"""Command-line CEQAnet operator archive builder.

This CLI creates a deterministic ZIP archive from a verified local CEQAnet
operator export directory. It performs no network requests, database access, or
persistence mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_operator_archive import build_ceqanet_operator_archive

app = typer.Typer(help="Build deterministic CEQAnet operator export archives.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Build deterministic CEQAnet operator export archives."""


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
    """Render a compact archive summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    table = Table(title="CEQAnet Operator Archive")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "schema_version",
        "archive_path",
        "source_dir",
        "file_count",
        "byte_count",
        "sha256",
        "verification_passed",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        table.add_row(field_name, str(metadata.get(field_name)))
    console.print(table)


@app.command("build")
def build_operator_archive(
    source_dir: Annotated[
        Path,
        typer.Option(
            "--source-dir",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Verified CEQAnet operator export directory.",
        ),
    ],
    archive_path: Annotated[
        Path,
        typer.Option("--archive", help="ZIP archive path to write."),
    ],
    allow_unverified: Annotated[
        bool,
        typer.Option(
            "--allow-unverified",
            help="Allow archive creation even when bundle verification fails.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable archive JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write archive JSON to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Build a deterministic ZIP archive from a CEQAnet operator export directory."""

    _reject_output_without_json(output_path, json_output)
    try:
        payload = build_ceqanet_operator_archive(
            source_dir=source_dir,
            archive_path=archive_path,
            require_verified=not allow_unverified,
        ).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet operator archive JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_summary(payload)
