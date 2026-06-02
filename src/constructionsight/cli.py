"""Command-line interface for ConstructionSight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.models import PublicSource
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore

app = typer.Typer(help="ConstructionSight lawful public-record intelligence tools.")
console = Console()


def _load_sources_from_json(registry_path: Path) -> list[PublicSource]:
    """Load and validate source records from a JSON registry file."""

    data = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Source registry JSON must be a list of source records.")
    return [PublicSource.model_validate(item) for item in data]


def _render_source_table(sources: list[PublicSource], title: str) -> None:
    """Render a concise source-registry table."""

    table = Table(title=title)
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

    sources = _load_sources_from_json(registry_path)
    _render_source_table(sources, "ConstructionSight Source Registry")
    console.print(f"Validated {len(sources)} source records.")


@app.command("init-db")
def init_db(
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."),
    ] = None,
) -> None:
    """Initialize the ConstructionSight database tables."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    console.print("Database initialized.")


@app.command("load-sources")
def load_sources(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."),
    ] = None,
) -> None:
    """Load source registry records into the database."""

    sources = _load_sources_from_json(registry_path)
    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        count = SourceRegistryStore(session).upsert_many(sources)

    console.print(f"Loaded {count} source records.")


@app.command("list-sources")
def list_sources(
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."),
    ] = None,
) -> None:
    """List source registry records from the database."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        sources = SourceRegistryStore(session).list_sources()

    _render_source_table(sources, "Persisted ConstructionSight Sources")
    console.print(f"Found {len(sources)} source records.")
