"""Command-line universal lawful intake inspector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.intake_service import inspect_lawful_file
from constructionsight.storage.runtime_artifacts import write_runtime_text

app = typer.Typer(help="Inspect lawful digital inputs through universal intake.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Inspect lawful digital inputs through universal intake."""


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
    """Render a compact intake summary."""

    evidence = cast(dict[str, object], payload["evidence"])
    detection = cast(dict[str, object], payload["format_detection"])
    facts = cast(list[dict[str, object]], payload["extracted_facts"])
    fragments = cast(list[dict[str, object]], payload["unmapped_fragments"])

    table = Table(title="Universal Intake Inspection")
    table.add_column("Field")
    table.add_column("Value")
    for field_name, value in (
        ("intake_id", payload.get("intake_id")),
        ("evidence_id", evidence.get("evidence_id")),
        ("source_name", evidence.get("source_name")),
        ("format_family", detection.get("format_family")),
        ("understanding_status", payload.get("understanding_status")),
        ("routing", payload.get("routing")),
        ("byte_count", evidence.get("byte_count")),
        ("sha256", evidence.get("sha256")),
        ("extracted_fact_count", len(facts)),
        ("unmapped_fragment_count", len(fragments)),
        ("next_action", payload.get("next_action")),
    ):
        table.add_row(field_name, str(value))
    console.print(table)

    if facts:
        fact_table = Table(title="Extracted Material Facts")
        fact_table.add_column("Kind")
        fact_table.add_column("Value")
        fact_table.add_column("Normalized")
        fact_table.add_column("Confidence")
        for fact in facts:
            fact_table.add_row(
                str(fact.get("fact_kind") or ""),
                str(fact.get("value") or ""),
                str(fact.get("normalized_value") or ""),
                str(fact.get("confidence") or ""),
            )
        console.print(fact_table)


@app.command("inspect")
def inspect_input(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Lawful digital input file to inspect.",
        ),
    ],
    source_name: Annotated[
        str | None,
        typer.Option("--source-name", help="Human-readable source name."),
    ] = None,
    source_family: Annotated[
        str | None,
        typer.Option("--source-family", help="Optional source family hint."),
    ] = None,
    source_url: Annotated[
        str | None,
        typer.Option("--source-url", help="Optional source URL."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable intake JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write intake JSON to a file. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Inspect a lawful input file and classify its intake route."""

    _reject_output_without_json(output_path, json_output)
    payload = inspect_lawful_file(
        input_path,
        source_name=source_name,
        source_family=source_family,
        source_url=source_url,
    ).to_dict()

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote universal intake JSON to {output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    _render_summary(payload)
