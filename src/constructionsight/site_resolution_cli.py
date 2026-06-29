"""Command-line site-resolution tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.intake_models import UniversalIntakeRecord
from constructionsight.site_resolution_service import resolve_site_from_intake

app = typer.Typer(help="Resolve site and parcel anchors from universal intake JSON.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Resolve site and parcel anchors from universal intake JSON."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_intake_record(input_path: Path) -> UniversalIntakeRecord:
    """Load a universal intake JSON file."""

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    return UniversalIntakeRecord.model_validate(payload)


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact site-resolution summary."""

    table = Table(title="Site Resolution")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "resolution_id",
        "source_name",
        "evidence_id",
        "status",
        "primary_site_key",
    ):
        table.add_row(field_name, str(payload.get(field_name)))
    console.print(table)

    candidates = cast(list[dict[str, object]], payload.get("candidates", []))
    if candidates:
        candidate_table = Table(title="Site Candidates")
        candidate_table.add_column("Site Key")
        candidate_table.add_column("Score")
        candidate_table.add_column("Strength")
        candidate_table.add_column("APN")
        candidate_table.add_column("Address")
        for candidate in candidates:
            candidate_table.add_row(
                str(candidate.get("site_key") or ""),
                str(candidate.get("confidence_score") or ""),
                str(candidate.get("match_strength") or ""),
                str(candidate.get("apn") or ""),
                str(candidate.get("address") or ""),
            )
        console.print(candidate_table)


@app.command("resolve-intake")
def resolve_intake(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Universal intake JSON file to resolve.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable resolution JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write site-resolution JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Resolve a site/parcel anchor from one universal intake JSON file."""

    _reject_output_without_json(output_path, json_output)
    result = resolve_site_from_intake(_load_intake_record(input_path)).to_dict()

    if output_path is not None:
        _write_json_file(output_path, result)
        typer.echo(f"Wrote site-resolution JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(result, indent=2, sort_keys=True, default=str))
        return
    _render_summary(result)
