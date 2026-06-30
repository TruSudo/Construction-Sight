"""Source verification checklist CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_source_observation_templates,
    build_source_verification_checklist_report,
)

app = typer.Typer(help="ConstructionSight source verification checklist tools.")
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
def source_verification_root() -> None:
    """ConstructionSight source verification commands."""


@app.command("observation-template")
def source_observation_template(
    registry_path: Annotated[Path, typer.Argument(help="Path to source registry JSON.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional output path for editable JSON template."),
    ] = None,
) -> None:
    """Build an editable observation JSON template without changing the registry."""

    templates = build_source_observation_templates(_load_sources_from_json(registry_path))
    payload = [template.model_dump(mode="json") for template in templates]
    rendered = json.dumps(payload, indent=2)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        console.print(f"Wrote source observation template to {output}")
        return
    console.print_json(rendered)


@app.command("checklist")
def source_verification_checklist(
    registry_path: Annotated[Path, typer.Argument(help="Path to source registry JSON.")],
    observations_path: Annotated[
        Path | None,
        typer.Option("--observations-path", help="Optional operator observation JSON list."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
    check_http: Annotated[bool, typer.Option("--check-http")] = False,
) -> None:
    """Build a report-only manual source-verification checklist."""

    report = build_source_verification_checklist_report(
        _load_sources_from_json(registry_path),
        default_adapter_family_specs(),
        check_http=check_http,
        observations=_load_observations(observations_path),
    )
    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return

    summary = Table(title="ConstructionSight Source Verification Checklist")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(report.source_count))
    for status, count in sorted(report.status_counts.items()):
        summary.add_row(status, str(count))
    console.print(summary)

    rows = Table(title="Source Verification Checklist Rows")
    rows.add_column("Source")
    rows.add_column("Status")
    rows.add_column("Entry")
    rows.add_column("Query")
    rows.add_column("List")
    rows.add_column("Detail")
    rows.add_column("Next action")
    for row in report.rows:
        rows.add_row(
            row.source_name,
            row.checklist_status.value,
            row.public_entry_page.value,
            row.query_behavior.value,
            row.result_list.value,
            row.detail_page.value,
            row.next_action,
        )
    console.print(rows)
