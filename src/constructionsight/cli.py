"""Command-line interface for ConstructionSight."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import (
    audit_adapter_contracts,
    default_adapter_family_specs,
    default_adapter_registry,
)
from constructionsight.adapters.base import AdapterRunContext
from constructionsight.adapters.runner import AdapterRunner
from constructionsight.models import PublicSource
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore
from constructionsight.verification.source_verifier import SourceVerifier

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


@app.command("audit-adapters")
def audit_adapters() -> None:
    """Audit adapter registry/spec alignment."""

    result = audit_adapter_contracts(
        default_adapter_registry(),
        default_adapter_family_specs(),
    )

    table = Table(title="Adapter Contract Audit")
    table.add_column("Check")
    table.add_column("Result")

    table.add_row("Registry platforms", str(len(result.registry_platforms)))
    table.add_row("Spec platforms", str(len(result.spec_platforms)))
    table.add_row(
        "Missing specs",
        ", ".join(platform.value for platform in result.missing_specs) or "none",
    )
    table.add_row(
        "Missing registrations",
        ", ".join(platform.value for platform in result.missing_registrations) or "none",
    )
    table.add_row("Passed", str(result.passed))

    console.print(table)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("dry-run-adapters")
def dry_run_adapters(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
    limit: Annotated[int | None, typer.Option(help="Maximum number of sources to dry-run.")] = None,
    max_records: Annotated[int | None, typer.Option(help="Maximum records per adapter.")] = 0,
) -> None:
    """Run registered adapters in dry-run mode against a source registry."""

    sources = _load_sources_from_json(registry_path)
    if limit is not None:
        sources = sources[:limit]

    runner = AdapterRunner(default_adapter_registry())
    context = AdapterRunContext(dry_run=True, max_records=max_records)

    table = Table(title="Adapter Dry Run")
    table.add_column("Source")
    table.add_column("Platform")
    table.add_column("Outcome")
    table.add_column("Records")
    table.add_column("Errors")

    for source in sources:
        result = runner.run_source(source, context)
        table.add_row(
            source.source_name,
            source.platform_family.value,
            result.outcome.value,
            str(len(result.records)),
            str(len(result.errors)),
        )

    console.print(table)
    console.print(f"Dry-ran {len(sources)} adapter sources.")


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


@app.command("verify-sources")
def verify_sources(
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."),
    ] = None,
    limit: Annotated[int | None, typer.Option(help="Maximum number of sources to verify.")] = None,
) -> None:
    """Verify persisted public sources and store auditable verification results."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    verifier = SourceVerifier()

    table = Table(title="Source Verification Results")
    table.add_column("Source")
    table.add_column("Reachable")
    table.add_column("Detected Platform")
    table.add_column("Search")
    table.add_column("Login")
    table.add_column("Confidence")

    with managed_session(factory) as session:
        sources = SourceRegistryStore(session).list_sources()
        if limit is not None:
            sources = sources[:limit]
        store = VerificationStore(session)
        for source in sources:
            result = verifier.verify(source)
            store.add_result(result)
            table.add_row(
                result.source_name,
                str(result.url_reachable),
                result.portal_type_detected.value,
                str(result.public_search_available),
                str(result.login_required),
                str(result.confidence_score),
            )

    console.print(table)
    console.print(f"Verified {len(sources)} source records.")
