"""Read-safe operator CLI for persisted upstream intelligence records."""

from __future__ import annotations

import json
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.upstream_operator_models import UpstreamOperatorRecordKind
from constructionsight.upstream_operator_service import (
    UpstreamOperatorError,
    get_upstream_operator_record,
    list_upstream_operator_records,
)

app = typer.Typer(help="ConstructionSight persisted upstream record tools.")
console = Console()


def _database_factory(database_url: str | None) -> sessionmaker[Session]:
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return session_factory(engine)


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=2)


@app.callback()
def upstream_operator_root() -> None:
    """Inspect persisted upstream intelligence without mutating evidence."""


@app.command("list")
def list_records(
    record_kind: Annotated[
        UpstreamOperatorRecordKind,
        typer.Argument(help="Persisted upstream record family to list."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL."),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(min=1, max=1000, help="Maximum records to return."),
    ] = 100,
    status: Annotated[
        str | None,
        typer.Option(help="Exact indexed status filter."),
    ] = None,
    source_key: Annotated[
        str | None,
        typer.Option(help="Exact source key filter."),
    ] = None,
    source_record_id: Annotated[
        str | None,
        typer.Option(help="Exact source record identifier filter."),
    ] = None,
    site_key: Annotated[
        str | None,
        typer.Option(help="Exact site or primary-site key filter."),
    ] = None,
    apn: Annotated[
        str | None,
        typer.Option(help="Exact APN filter."),
    ] = None,
    county: Annotated[
        str | None,
        typer.Option(help="Exact county filter."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    """List newest persisted upstream records using supported filters."""

    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            records = list_upstream_operator_records(
                session,
                record_kind,
                limit=limit,
                status=status,
                source_key=source_key,
                source_record_id=source_record_id,
                site_key=site_key,
                apn=apn,
                county=county,
            )
    except UpstreamOperatorError as exc:
        _fail(str(exc))
    if json_output:
        console.print_json(json.dumps([record.to_dict() for record in records]))
        return
    table = Table(title=f"ConstructionSight Upstream Records: {record_kind.value}")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Source")
    table.add_column("Source record")
    table.add_column("Site")
    table.add_column("APN")
    table.add_column("County")
    table.add_column("Confidence")
    table.add_column("Observed")
    for record in records:
        confidence = (
            "" if record.confidence_score is None else str(record.confidence_score)
        )
        table.add_row(
            record.record_id,
            record.status or "",
            record.source_key or "",
            record.source_record_id or "",
            record.site_key or "",
            record.apn or "",
            record.county or "",
            confidence,
            record.observed_at or "",
        )
    console.print(table)


@app.command("detail")
def record_detail(
    record_kind: Annotated[
        UpstreamOperatorRecordKind,
        typer.Argument(help="Persisted upstream record family."),
    ],
    record_id: Annotated[
        str,
        typer.Argument(help="Canonical persisted record identifier."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    """Show one normalized envelope and its complete preserved payload."""

    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            record = get_upstream_operator_record(session, record_kind, record_id)
    except UpstreamOperatorError as exc:
        _fail(str(exc))
    if record is None:
        _fail(f"{record_kind.value} record not found: {record_id}")
    if json_output:
        console.print_json(json.dumps(record.to_dict()))
        return
    summary = Table(title=f"ConstructionSight Upstream Record: {record_kind.value}")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Record ID", record.record_id)
    summary.add_row("Status", record.status or "")
    summary.add_row("Source", record.source_key or "")
    summary.add_row("Source record", record.source_record_id or "")
    summary.add_row("Site", record.site_key or "")
    summary.add_row("APN", record.apn or "")
    summary.add_row("County", record.county or "")
    confidence = "" if record.confidence_score is None else str(record.confidence_score)
    summary.add_row("Confidence", confidence)
    summary.add_row("Observed", record.observed_at or "")
    console.print(summary)
    console.print_json(json.dumps(record.payload))
