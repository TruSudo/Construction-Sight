"""Operator CLI for authoritative result-ledger inspection and correction."""

from __future__ import annotations

import json
from datetime import date
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.result_authority_service import (
    ResultAuthorityError,
    apply_authoritative_result,
    list_result_authority_events,
    load_result_authority_snapshot,
)
from constructionsight.result_ledger_models import ResultLedgerStatus
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)

app = typer.Typer(help="ConstructionSight authoritative result-ledger operator tools.")
console = Console()


def _database_factory(database_url: str | None) -> sessionmaker[Session]:
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return session_factory(engine)


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=2)


def _expected_ledger(value: str) -> str | None:
    normalized = value.strip()
    if not normalized:
        _fail("--expected-current-ledger-id must not be blank; use 'none' for no result.")
    if normalized.lower() == "none":
        return None
    return normalized


def _decided_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ResultAuthorityError("--decided-date must use ISO format YYYY-MM-DD") from exc


@app.callback()
def result_authority_root() -> None:
    """Inspect result history and apply stale-state-protected corrections."""


@app.command("current")
def current_result(
    workflow_id: Annotated[
        str,
        typer.Argument(help="Persisted lead workflow identifier."),
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
    """Show the validated authoritative result tip for one workflow."""

    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            snapshot = load_result_authority_snapshot(session, workflow_id)
    except ValueError as exc:
        _fail(str(exc))
    if snapshot is None:
        _fail(f"result ledger history not found for workflow: {workflow_id}")
    payload = snapshot.to_dict()
    if json_output:
        console.print_json(json.dumps(payload))
        return
    table = Table(title="ConstructionSight Authoritative Result")
    table.add_column("Workflow")
    table.add_column("Ledger")
    table.add_column("Revision")
    table.add_column("Status")
    table.add_column("Share state")
    table.add_column("Head persisted")
    table.add_row(
        snapshot.workflow_id,
        snapshot.current.ledger_id,
        str(snapshot.current.revision),
        snapshot.current.status.value,
        snapshot.current.share_status.value,
        "yes" if snapshot.head is not None else "no (history-derived)",
    )
    console.print(table)


@app.command("history")
def result_history(
    workflow_id: Annotated[
        str,
        typer.Argument(help="Persisted lead workflow identifier."),
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
    """Show all immutable result revisions and operator authority events."""

    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            snapshot = load_result_authority_snapshot(session, workflow_id)
            events = list_result_authority_events(session, workflow_id)
    except ValueError as exc:
        _fail(str(exc))
    if snapshot is None:
        _fail(f"result ledger history not found for workflow: {workflow_id}")
    payload = {
        "snapshot": snapshot.to_dict(),
        "authority_events": [event.to_dict() for event in events],
    }
    if json_output:
        console.print_json(json.dumps(payload))
        return
    table = Table(title="ConstructionSight Result History")
    table.add_column("Revision")
    table.add_column("Ledger")
    table.add_column("Status")
    table.add_column("Supersedes")
    table.add_column("Correction reason")
    for ledger in snapshot.history:
        table.add_row(
            str(ledger.revision),
            ledger.ledger_id,
            ledger.status.value,
            ledger.supersedes_ledger_id or "",
            ledger.correction_reason or "",
        )
    console.print(table)
    event_table = Table(title="ConstructionSight Result Authority Events")
    event_table.add_column("Revision")
    event_table.add_column("Event")
    event_table.add_column("Previous")
    event_table.add_column("Current")
    event_table.add_column("Reason")
    for event in events:
        event_table.add_row(
            str(event.revision),
            event.event_id,
            event.previous_ledger_id or "",
            event.current_ledger_id,
            event.reason,
        )
    console.print(event_table)


@app.command("record")
def record_result(
    workflow_id: Annotated[
        str,
        typer.Argument(help="Persisted lead workflow identifier."),
    ],
    status: Annotated[
        ResultLedgerStatus,
        typer.Argument(help="Authoritative result status to record."),
    ],
    expected_current_ledger_id: Annotated[
        str,
        typer.Option(
            "--expected-current-ledger-id",
            help=(
                "Required stale-state guard. Supply the reviewed ledger ID, or "
                "the literal 'none' when creating the first result."
            ),
        ),
    ],
    authority_reason: Annotated[
        str,
        typer.Option(
            "--reason",
            help="Required audit reason authorizing the initial result or correction.",
        ),
    ],
    decided_date: Annotated[
        str | None,
        typer.Option(
            "--decided-date",
            help="Optional result date in ISO format YYYY-MM-DD.",
        ),
    ] = None,
    gross_value: Annotated[
        float | None,
        typer.Option(help="Optional won-result gross value, limited to cents."),
    ] = None,
    share_rate: Annotated[
        float | None,
        typer.Option(help="Optional won-result share rate from 0 through 1."),
    ] = None,
    outcome_reason: Annotated[
        list[str] | None,
        typer.Option(
            "--outcome-reason",
            help="Repeatable evidence-backed reason describing the business outcome.",
        ),
    ] = None,
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL."),
    ] = None,
    apply_changes: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Explicitly authorize the persisted result selection or correction.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    """Create or correct one result through the serialized authority service."""

    if not apply_changes:
        _fail("Explicit --apply authorization is required.")
    expected = _expected_ledger(expected_current_ledger_id)
    try:
        parsed_date = _decided_date(decided_date)
        factory = _database_factory(database_url)
        with managed_session(factory) as session:
            report = apply_authoritative_result(
                session,
                workflow_id=workflow_id,
                expected_current_ledger_id=expected,
                status=status,
                authority_reason=authority_reason,
                decided_date=parsed_date,
                gross_value=gross_value,
                share_rate=share_rate,
                outcome_reasons=outcome_reason,
            )
    except ValueError as exc:
        _fail(str(exc))
    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return
    table = Table(title="ConstructionSight Result Authority Update")
    table.add_column("Workflow")
    table.add_column("Previous ledger")
    table.add_column("Current ledger")
    table.add_column("Revision")
    table.add_column("Status")
    table.add_column("Event")
    table.add_row(
        workflow_id,
        report.previous_ledger_id or "none",
        report.current.ledger_id,
        str(report.current.revision),
        report.current.status.value,
        report.event.event_id,
    )
    console.print(table)
