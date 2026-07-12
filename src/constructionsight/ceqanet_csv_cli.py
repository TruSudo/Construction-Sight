"""Operator CLI for offline CEQAnet official CSV planning and inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
    inspect_ceqanet_csv_bytes,
    parse_ceqanet_csv_export_url,
)

app = typer.Typer(
    help="Plan and inspect source-provided CEQAnet CSV exports without network access."
)
console = Console()


@app.callback()
def ceqanet_csv_root() -> None:
    """ConstructionSight CEQAnet official CSV contract commands."""


@app.command("plan")
def plan_csv_export(
    sch_number: Annotated[
        str,
        typer.Option("--sch-number", help="Exact 10-digit CEQAnet SCH number."),
    ],
    document_id: Annotated[
        int | None,
        typer.Option("--document-id", min=1, help="Optional positive document ID."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional JSON artifact output path."),
    ] = None,
) -> None:
    """Build a deterministic official CSV URL identity without making a request."""

    try:
        request = build_ceqanet_csv_export_request(
            sch_number=sch_number,
            document_id=document_id,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit_json(request.model_dump(mode="json"), output)


@app.command("inspect-file")
def inspect_csv_file(
    csv_path: Annotated[Path, typer.Argument(help="Path to an already-obtained CSV file.")],
    source_url: Annotated[
        str,
        typer.Option("--source-url", help="Exact official CEQAnet CSV URL identity."),
    ],
    content_type: Annotated[
        str | None,
        typer.Option("--content-type", help="Optional observed response Content-Type."),
    ] = None,
    max_retained_rows: Annotated[
        int,
        typer.Option(
            "--max-retained-rows",
            min=0,
            help="Maximum normalized rows retained in the JSON inspection artifact.",
        ),
    ] = 1_000,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional JSON inspection output path."),
    ] = None,
) -> None:
    """Inspect a local CSV body without network access or persistence mutation."""

    try:
        request = parse_ceqanet_csv_export_url(source_url)
        content = csv_path.read_bytes()
        inspection = inspect_ceqanet_csv_bytes(
            request,
            content,
            content_type=content_type,
            max_retained_rows=max_retained_rows,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit_json(inspection.model_dump(mode="json"), output)


def _emit_json(payload: object, output: Path | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        console.print(f"Wrote CEQAnet CSV artifact to {output}")
        return
    console.print_json(rendered)


if __name__ == "__main__":
    app()
