"""Source readiness workflow CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.models import PublicSource
from constructionsight.source_readiness_service import (
    build_authorized_source_readiness_report,
    build_source_readiness_report,
)

app = typer.Typer(help="ConstructionSight source-readiness tools.")
console = Console()


def _load_sources_from_json(registry_path: Path) -> list[PublicSource]:
    """Load source records from a JSON registry file."""

    data: Any = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Source registry JSON must be a list of source records.")
    return [PublicSource.model_validate(item) for item in data]


@app.callback()
def source_readiness_root() -> None:
    """ConstructionSight source-readiness commands."""


@app.command("check")
def source_readiness_check(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
    check_http: Annotated[
        bool,
        typer.Option(
            "--check-http",
            help=(
                "Additional confirmation for bounded live reachability checks. "
                "This Boolean is not the operative authorization decision."
            ),
        ),
    ] = False,
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
            help="Reason for the exact source-set reachability authorization.",
        ),
    ] = "Perform one reviewed source-readiness reachability check.",
) -> None:
    """Build a conservative report; authorize only the optional HTTP branch."""

    sources = _load_sources_from_json(registry_path)
    adapter_specs = default_adapter_family_specs()
    try:
        report = (
            build_authorized_source_readiness_report(
                sources,
                adapter_specs,
                caller_confirmation=True,
                authorization_reason=authorization_reason,
                operator_id=operator_id,
            )
            if check_http
            else build_source_readiness_report(
                sources,
                adapter_specs,
                check_http=False,
            )
        )
    except (AuthorizationDeniedError, ValueError) as exc:
        typer.echo(f"Source readiness check blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return
    summary = Table(title="ConstructionSight Source Readiness")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(report.source_count))
    for status, count in sorted(report.status_counts.items()):
        summary.add_row(status, str(count))
    console.print(summary)

    rows = Table(title="Source Readiness Rows")
    rows.add_column("Source")
    rows.add_column("Platform")
    rows.add_column("Verification")
    rows.add_column("Adapter")
    rows.add_column("Readiness")
    rows.add_column("HTTP")
    rows.add_column("Next action")
    for row in report.rows:
        http_status = "not_checked"
        if row.http_reachability.checked:
            http_status = str(
                row.http_reachability.status_code or row.http_reachability.error
            )
        rows.add_row(
            row.source_name,
            row.platform_family,
            row.verification_status,
            row.adapter_status,
            row.readiness_status.value,
            http_status,
            row.next_action,
        )
    console.print(rows)
