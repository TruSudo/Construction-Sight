"""Command-line CEQAnet persistence execution.

This CLI applies an existing CEQAnet write plan to normalized SQLite persistence
only after explicit operator consent. It performs no network requests and no
document downloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_persistence_execute import execute_ceqanet_write_plan
from constructionsight.storage.database import create_database_engine, database_url_from_path

app = typer.Typer(help="Execute guarded CEQAnet persistence write plans.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Execute guarded CEQAnet persistence write plans."""


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


def _database_url(database_url: str | None, database_path: Path | None) -> str:
    """Resolve database URL from mutually exclusive CLI options."""

    if database_url is not None and database_path is not None:
        raise typer.BadParameter("Use either --database-url or --database-path, not both.")
    if database_url is not None:
        return database_url
    if database_path is not None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return database_url_from_path(database_path)
    raise typer.BadParameter("A target database must be supplied with --database-url or --database-path.")


def _execute_payload(write_plan_payload: dict[str, Any], *, database_url: str) -> dict[str, object]:
    """Execute write plan and convert validation errors to CLI errors."""

    try:
        engine = create_database_engine(database_url)
        return execute_ceqanet_write_plan(write_plan_payload, engine=engine).to_dict()
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
        typer.echo(f"Wrote CEQAnet persistence execution JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact persistence execution summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    summary = Table(title="CEQAnet Persistence Execution")
    summary.add_column("Field")
    summary.add_column("Value")
    for field_name in (
        "schema_version",
        "applied_count",
        "failed_count",
        "skipped_count",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        summary.add_row(field_name, str(metadata.get(field_name)))
    console.print(summary)

    applied = cast(list[dict[str, object]], payload["applied_operations"])
    if applied:
        table = Table(title="Applied Operations")
        table.add_column("Operation ID")
        table.add_column("Target")
        table.add_column("Key")
        for operation in applied:
            table.add_row(
                str(operation.get("operation_id") or ""),
                str(operation.get("target_collection") or ""),
                str(operation.get("target_key") or ""),
            )
        console.print(table)


@app.command("execute")
def execute_persistence_plan(
    write_plan_path: Annotated[
        Path,
        typer.Option(
            "--write-plan",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet write plan JSON.",
        ),
    ],
    database_url: Annotated[
        str | None,
        typer.Option("--database-url", help="SQLAlchemy database URL to mutate."),
    ] = None,
    database_path: Annotated[
        Path | None,
        typer.Option("--database-path", help="SQLite database path to mutate."),
    ] = None,
    execute_write: Annotated[
        bool,
        typer.Option("--execute-write", help="Required explicit consent for persistence mutation."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Execute a CEQAnet write plan against normalized persistence."""

    _reject_output_without_json(output_path, json_output)
    if not execute_write:
        typer.echo("Refusing persistence execution without --execute-write.")
        raise typer.Exit(code=1)

    resolved_database_url = _database_url(database_url, database_path)
    write_plan_payload = _load_json_object(write_plan_path)
    payload = _execute_payload(write_plan_payload, database_url=resolved_database_url)
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {
        "write_plan_path": str(write_plan_path),
        "database_url": resolved_database_url,
    }

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
