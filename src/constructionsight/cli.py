"""Command-line interface for ConstructionSight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.models import PublicSource

app = typer.Typer(help="ConstructionSight lawful public-record intelligence tools.")
console = Console()


@app.command()
def version() -> None:
    """Print the installed ConstructionSight version."""

    from constructionsight import __version__

    console.print(__version__)


@app.command("validate-sources")
def validate_sources(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
) -> None:
    """Validate a JSON source registry against the phase-1 schema."""

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Source registry JSON must be a list of source records.")

    sources = [PublicSource.model_validate(item) for item in data]

    table = Table(title="ConstructionSight Source Registry")
    table.add_column("Source")
    table.add_column("Jurisdiction")
    table.add_column("Platform")
    table.add_column("Status")
    table.add_column("Confidence")

    for source in sources:
        table.add_row(
            source.source_name,
            source.jurisdiction.name,
            source.platform_family.value,
            source.verification_status.value,
            str(source.confidence_score),
        )

    console.print(table)
    console.print(f"Validated {len(sources)} source records.")
