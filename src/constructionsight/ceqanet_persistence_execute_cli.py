"""Command-line atomic CEQAnet persistence execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.operator_services.ceqanet_persistence_service import (
    execute_authorized_ceqanet_write_plan,
)
from constructionsight.storage.database import database_url_from_path
from constructionsight.storage.runtime_artifacts import read_runtime_text

app = typer.Typer(help="Execute authorized atomic CEQAnet persistence write plans.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Execute authorized atomic CEQAnet persistence write plans."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_json_object(input_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(read_runtime_text(input_path))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"{input_path} is not valid readable JSON.") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _database_url(database_url: str | None, database_path: Path | None) -> str:
    if database_url is not None and database_path is not None:
        raise typer.BadParameter("Use either --database-url or --database-path, not both.")
    if database_url is not None:
        return database_url
    if database_path is not None:
        return database_url_from_path(database_path)
    raise typer.BadParameter(
        "A target database must be supplied with --database-url or --database-path."
    )


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _write_or_print_json(payload: dict[str, object], output_path: Path | None) -> None:
    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet persistence execution JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, object]) -> None:
    metadata = cast(dict[str, object], payload["metadata"])
    summary = Table(title="CEQAnet Persistence Execution")
    summary.add_column("Field")
    summary.add_column("Value")
    for field_name in (
        "schema_version",
        "transactional",
        "applied_count",
        "failed_count",
        "skipped_count",
        "network_executed",
        "database_opened",
        "persistence_mutated",
    ):
        summary.add_row(field_name, str(metadata.get(field_name)))
    authorization = cast(dict[str, object], payload["authorization"])
    summary.add_row("authorization_decision", str(authorization["decision_id"]))
    summary.add_row("authorization_preflight", str(authorization["preflight_id"]))
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
            help="Existing reviewed CEQAnet write plan JSON.",
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
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help="Optional local audit identity; this is not authentication.",
        ),
    ] = None,
    authorization_reason: Annotated[
        str,
        typer.Option(
            "--authorization-reason",
            help="Reason for this exact reviewed write-plan transaction.",
        ),
    ] = "Apply one reviewed CEQAnet write plan atomically.",
    execute_write: Annotated[
        bool,
        typer.Option(
            "--execute-write",
            help=(
                "Additional caller confirmation. This Boolean is not the operative "
                "authorization decision."
            ),
        ),
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
    """Authorize and atomically execute one CEQAnet write plan."""

    if not execute_write:
        typer.echo(
            "Refusing persistence execution without --execute-write; caller "
            "confirmation is required in addition to scope-bound authority.",
            err=True,
        )
        raise typer.Exit(code=1)
    _reject_output_without_json(output_path, json_output)
    resolved_database_url = _database_url(database_url, database_path)
    try:
        result = execute_authorized_ceqanet_write_plan(
            write_plan_payload=_load_json_object(write_plan_path),
            database_url=resolved_database_url,
            caller_confirmation=True,
            authorization_reason=authorization_reason,
            operator_id=operator_id,
        )
    except (AuthorizationDeniedError, RuntimeError, ValueError) as exc:
        typer.echo(f"CEQAnet persistence execution blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    payload = result.execution.to_dict()
    payload["authorization"] = result.authorization.to_dict()
    payload["input"] = {
        "write_plan_path": str(write_plan_path),
        "database_destination_digest_only": True,
    }
    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
