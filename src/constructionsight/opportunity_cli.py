"""Command-line opportunity candidate inspector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.intake_models import UniversalIntakeRecord
from constructionsight.opportunity_service import build_opportunity_candidate
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="Convert universal intake records into opportunity candidates.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Convert universal intake records into opportunity candidates."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_intake_record(input_path: Path) -> UniversalIntakeRecord:
    """Load a universal intake JSON file."""

    payload = json.loads(read_runtime_text(input_path))
    return UniversalIntakeRecord.model_validate(payload)


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""
    write_runtime_text(
        output_path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact opportunity-candidate summary."""

    events = cast(list[dict[str, object]], payload["transition_events"])
    table = Table(title="Opportunity Candidate")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "candidate_id",
        "intake_id",
        "evidence_id",
        "source_name",
        "lead_score",
        "readiness",
        "priority",
        "confidence_band",
        "recommended_action",
    ):
        table.add_row(field_name, str(payload.get(field_name)))
    console.print(table)

    if events:
        event_table = Table(title="Transition Events")
        event_table.add_column("Kind")
        event_table.add_column("Score")
        event_table.add_column("Label")
        for event in events:
            event_table.add_row(
                str(event.get("event_kind") or ""),
                str(event.get("score_delta") or ""),
                str(event.get("label") or ""),
            )
        console.print(event_table)


@app.command("evaluate")
def evaluate_intake(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Universal intake JSON file to evaluate.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable candidate JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write candidate JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Evaluate one universal intake JSON file as an opportunity candidate."""

    _reject_output_without_json(output_path, json_output)
    candidate = build_opportunity_candidate(_load_intake_record(input_path)).to_dict()

    if output_path is not None:
        _write_json_file(output_path, candidate)
        typer.echo(f"Wrote opportunity candidate JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(candidate, indent=2, sort_keys=True, default=str))
        return
    _render_summary(candidate)
