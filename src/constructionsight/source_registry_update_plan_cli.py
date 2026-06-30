"""Source registry update plan CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_registry_update_plan_service import (
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)

app = typer.Typer(help="ConstructionSight source registry update plan tools.")
console = Console()


def _load_sources_from_json(path: Path) -> list[PublicSource]:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Registry JSON must be a list.")
    return [PublicSource.model_validate(item) for item in data]


def _load_observations(path: Path | None) -> list[SourceVerificationObservation]:
    if path is None:
        return []
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Observation JSON must be a list.")
    return [SourceVerificationObservation.model_validate(item) for item in data]


@app.callback()
def source_registry_update_root() -> None:
    """ConstructionSight source registry update plan commands."""


@app.command("plan")
def source_registry_update_plan(
    registry_path: Annotated[Path, typer.Argument(help="Path to source registry JSON.")],
    observations_path: Annotated[
        Path | None,
        typer.Option("--observations-path", help="Optional operator observation JSON list."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional output path for plan JSON."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
    check_http: Annotated[bool, typer.Option("--check-http")] = False,
) -> None:
    """Build a dry-run source registry update plan without writing registry data."""

    report = build_source_registry_update_plan(
        _load_sources_from_json(registry_path),
        default_adapter_family_specs(),
        check_http=check_http,
        observations=_load_observations(observations_path),
    )
    rendered = json.dumps(report.to_dict(), indent=2)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        console.print(f"Wrote source registry update plan to {output}")
        return
    if json_output:
        console.print_json(rendered)
        return

    summary = Table(title="ConstructionSight Source Registry Update Plan")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(report.source_count))
    summary.add_row("Updates proposed", str(report.update_count))
    for action, count in sorted(report.action_counts.items()):
        summary.add_row(action, str(count))
    console.print(summary)

    rows = Table(title="Source Registry Update Plan Rows")
    rows.add_column("Source")
    rows.add_column("Current")
    rows.add_column("Proposed")
    rows.add_column("Update")
    rows.add_column("Next action")
    for row in report.rows:
        rows.add_row(
            row.source_name,
            row.current_verification_status,
            row.proposed_verification_status or "none",
            str(row.update_required),
            row.next_action,
        )
    console.print(rows)
