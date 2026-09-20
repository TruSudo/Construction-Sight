"""Explicit local CLI to inspect and stage, never approve, normalized source candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, NoReturn, cast

import typer

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.operator_dashboard_models import RecordKind
from constructionsight.storage.effect_consumption_store import EffectConsumptionError
from constructionsight.source_candidate_docket_service import (
    list_staged_source_candidates,
    preview_source_for_docket,
    stage_authorized_source_candidate,
)

app = typer.Typer(help="Explicit read/append-only normalized source review docket.")


def _kind(value: str) -> RecordKind:
    if value not in {"ceqa", "permit"}:
        raise ValueError("--kind must be exactly ceqa or permit")
    return cast(RecordKind, value)


def _fail(exc: Exception) -> NoReturn:
    typer.echo(f"Docket operation denied: {type(exc).__name__}: {exc}", err=True)
    raise typer.Exit(code=2)


@app.callback()
def main() -> None:
    """Show exact normalized source reviews or explicitly stage one unapproved copy."""


@app.command("preview")
def preview(
    database: Annotated[Path, typer.Option("--database", help="Existing SQLite file.")],
    kind: Annotated[str, typer.Option("--kind", help="Exact source family.")],
    record_id: Annotated[str, typer.Option("--record-id", help="Exact stored source key.")],
) -> None:
    """Display copyable current preview ID and normalized source digest without writes."""

    try:
        item = preview_source_for_docket(database, kind=_kind(kind), record_id=record_id)
    except (OSError, ValueError, LookupError) as exc:
        _fail(exc)
    typer.echo(json.dumps(item.model_dump(mode="json"), sort_keys=True, indent=2))


@app.command("stage")
def stage(
    database: Annotated[Path, typer.Option("--database", help="Existing SQLite file.")],
    kind: Annotated[str, typer.Option("--kind")],
    record_id: Annotated[str, typer.Option("--record-id")],
    preview_id: Annotated[str, typer.Option("--expected-preview-id")],
    source_sha256: Annotated[str, typer.Option("--expected-source-sha256")],
    reason: Annotated[str, typer.Option("--reason", help="Recorded local operator rationale.")],
    confirm: Annotated[
        bool, typer.Option("--confirm", help="Explicit scope confirmation.")
    ] = False,
    operator_id: Annotated[str | None, typer.Option("--operator-id")] = None,
) -> None:
    """Stage exactly one content-bound, unapproved local source snapshot."""

    try:
        outcome = stage_authorized_source_candidate(
            database,
            kind=_kind(kind),
            record_id=record_id,
            expected_preview_id=preview_id,
            expected_source_sha256=source_sha256,
            caller_confirmation=confirm,
            reason=reason,
            operator_id=operator_id,
        )
    except (
        AuthorizationDeniedError, EffectConsumptionError, OSError, ValueError, LookupError
    ) as exc:
        _fail(exc)
    typer.echo(json.dumps(outcome.entry.model_dump(mode="json"), sort_keys=True, indent=2))


@app.command("list")
def list_staged(
    database: Annotated[Path, typer.Option("--database", help="Existing SQLite file.")],
    kind: Annotated[str, typer.Option("--kind")],
    record_id: Annotated[str, typer.Option("--record-id")],
    limit: Annotated[int, typer.Option("--limit", min=1, max=100)] = 100,
) -> None:
    """Read integrity-checked retained revisions for one source-family/key pair."""

    try:
        rows = list_staged_source_candidates(
            database, kind=_kind(kind), record_id=record_id, limit=limit
        )
    except (OSError, ValueError, LookupError) as exc:
        _fail(exc)
    typer.echo(json.dumps(
        [entry.model_dump(mode="json") for entry in rows], sort_keys=True, indent=2
    ))
