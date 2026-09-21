"""Source promotion plan CLI."""

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
from constructionsight.operator_services.source_promotion_service import (
    build_authorized_source_promotion_plan,
)
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text

app = typer.Typer(help="ConstructionSight source promotion plan tools.")
console = Console()


def _load_sources_from_json(path: Path) -> list[PublicSource]:
    data: Any = json.loads(read_runtime_text(path))
    if not isinstance(data, list):
        raise typer.BadParameter("Registry JSON must be a list.")
    return [PublicSource.model_validate(item) for item in data]


def _load_observations(path: Path | None) -> list[SourceVerificationObservation]:
    if path is None:
        return []
    data: Any = json.loads(read_runtime_text(path))
    if not isinstance(data, list):
        raise typer.BadParameter("Observation JSON must be a list.")
    return [SourceVerificationObservation.model_validate(item) for item in data]


@app.callback()
def source_promotion_root() -> None:
    """ConstructionSight source promotion plan commands."""


@app.command("plan")
def source_promotion_plan(
    registry_path: Annotated[Path, typer.Argument(help="Path to source registry JSON.")],
    observations_path: Annotated[
        Path | None,
        typer.Option("--observations-path", help="Optional operator observation JSON list."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
    check_http: Annotated[bool, typer.Option("--check-http")] = False,
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help="Explicit local operator audit identity required with --check-http.",
        ),
    ] = None,
    authorization_reason: Annotated[
        str | None,
        typer.Option(
            "--authorization-reason",
            help="Nonblank reason required with --check-http.",
        ),
    ] = None,
) -> None:
    """Build a dry-run source promotion plan without registry mutation."""

    sources = _load_sources_from_json(registry_path)
    observations = _load_observations(observations_path)
    if check_http:
        if operator_id is None or not operator_id.strip():
            raise typer.BadParameter("--operator-id is required with --check-http")
        if authorization_reason is None or not authorization_reason.strip():
            raise typer.BadParameter("--authorization-reason is required with --check-http")
        try:
            report = build_authorized_source_promotion_plan(
                sources,
                default_adapter_family_specs(),
                observations=observations,
                caller_confirmation=True,
                authorization_reason=authorization_reason,
                operator_id=operator_id,
            )
        except (AuthorizationDeniedError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        report = build_source_promotion_plan(
            sources,
            default_adapter_family_specs(),
            check_http=False,
            observations=observations,
        )

    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return

    summary = Table(title="ConstructionSight Source Promotion Plan")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(report.source_count))
    for action, count in sorted(report.action_counts.items()):
        summary.add_row(action, str(count))
    console.print(summary)

    rows = Table(title="Source Promotion Plan Rows")
    rows.add_column("Source")
    rows.add_column("Checklist")
    rows.add_column("Action")
    rows.add_column("Proposed status")
    rows.add_column("Next action")
    for row in report.rows:
        rows.add_row(
            row.source_name,
            row.checklist_status,
            row.planned_action.value,
            row.proposed_registry_status or "none",
            row.next_action,
        )
    console.print(rows)
