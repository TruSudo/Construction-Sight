"""Review or explicitly apply genuine retained CEQAnet CSV records to an operator database.

This command never fetches sources or bypasses the existing atomic write authority.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy.orm import Session

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import canonical_digest
from constructionsight.ceqanet_csv_operator_bridge import (
    ReviewedCeqanetCsvBridge,
    build_reviewed_ceqanet_csv_bridge,
)
from constructionsight.operator_services.ceqanet_persistence_service import (
    execute_authorized_ceqanet_write_plan,
)
from constructionsight.storage.database import database_url_from_path
from constructionsight.storage.domain_store import CeqaStore
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="Review and explicitly import retained real CEQAnet CSV evidence.")


@app.callback()
def main() -> None:
    """Run a reviewed, bounded CSV-to-operator database workflow."""


def _load_evidence(path: Path) -> ReviewedCeqanetCsvBridge:
    try:
        payload: Any = json.loads(read_runtime_text(path))
        if not isinstance(payload, dict):
            raise ValueError("source execution artifact must contain a JSON object")
        # Historical evidence-series envelopes retain the live execution nested.
        content = payload.get("live_execution", payload)
        if not isinstance(content, dict):
            raise ValueError("live execution must contain a JSON object")
        execution = CeqanetCsvLiveExecution.model_validate(content)
        return build_reviewed_ceqanet_csv_bridge(execution)
    except (OSError, ValueError, TypeError) as exc:
        raise typer.BadParameter(
            f"retained CEQAnet source evidence could not be independently replayed: {exc}"
        ) from exc


def _plan_digest(bridge: ReviewedCeqanetCsvBridge) -> str:
    return canonical_digest(bridge.write_plan.to_dict())


def _summary(bridge: ReviewedCeqanetCsvBridge) -> dict[str, object]:
    return {
        "source_sha256": bridge.source_sha256,
        "source_execution_digest": bridge.source_execution_digest,
        "source_inspection_digest": bridge.source_inspection_digest,
        "approved_plan_digest_required": _plan_digest(bridge),
        "source_records": list(bridge.source_record_keys),
        "source_record_count": len(bridge.source_record_keys),
        "planned_write_count": bridge.write_plan.operation_count,
        "network_executed": False,
        "persistence_mutated": False,
        "qualified_leads_created": False,
        "read_only_operator_compatibility": "same existing SQLite domain store",
    }


@app.command("preview")
def preview(
    evidence_path: Annotated[
        Path,
        typer.Option(
            "--evidence", exists=True, dir_okay=False, readable=True,
            help="Existing complete, digest-bound CEQAnet CSV live execution JSON.",
        ),
    ],
    plan_output: Annotated[
        Path | None,
        typer.Option(
            "--plan-output", help="Optional path for exact reviewed write-plan JSON.",
        ),
    ] = None,
) -> None:
    """Independently replay public CSV evidence and preview all proposed writes."""

    bridge = _load_evidence(evidence_path)
    if plan_output is not None:
        write_runtime_text(
            plan_output,
            json.dumps(bridge.write_plan.to_dict(), indent=2, sort_keys=True) + "\n",
        )
    typer.echo(json.dumps(_summary(bridge), indent=2, sort_keys=True))


@app.command("apply")
def apply(
    evidence_path: Annotated[
        Path,
        typer.Option(
            "--evidence", exists=True, dir_okay=False, readable=True,
            help="Exact retained CSV execution JSON reviewed through preview.",
        ),
    ],
    database_path: Annotated[
        Path,
        typer.Option(
            "--database", exists=True, dir_okay=False, writable=True,
            help="An existing, operator-compatible SQLite database.",
        ),
    ],
    approved_source_sha256: Annotated[
        str,
        typer.Option("--approved-source-sha256", help="Exact source digest from preview."),
    ],
    approved_plan_digest: Annotated[
        str,
        typer.Option("--approved-plan-digest", help="Exact write-plan digest from preview."),
    ],
    authorization_reason: Annotated[
        str,
        typer.Option("--authorization-reason", help="Reason for importing this exact source."),
    ],
    execute_write: Annotated[
        bool,
        typer.Option("--execute-write", help="Explicit permission for one atomic persistence."),
    ] = False,
    operator_id: Annotated[
        str | None,
        typer.Option("--operator-id", help="Optional local audit identity, not authentication."),
    ] = None,
) -> None:
    """Apply only the reviewed exact plan through existing governed persistence."""

    if not execute_write:
        raise typer.BadParameter("explicit --execute-write is required")
    bridge = _load_evidence(evidence_path)
    if (
        approved_source_sha256 != bridge.source_sha256
        or approved_plan_digest != _plan_digest(bridge)
    ):
        raise typer.BadParameter("the retained source or write plan differs from reviewed hashes")
    if not authorization_reason.strip():
        raise typer.BadParameter("authorization reason cannot be blank")
    try:
        # Refuse a destination that the existing GUI cannot read; never migrate it
        # silently just to complete an import.
        engine = create_operator_read_engine(database_path)
        engine.dispose()
        result = execute_authorized_ceqanet_write_plan(
            write_plan_payload=bridge.write_plan.to_dict(),
            database_url=database_url_from_path(database_path),
            caller_confirmation=True,
            authorization_reason=authorization_reason,
            operator_id=operator_id,
        )
        if result.execution.applied_count != bridge.write_plan.operation_count:
            raise ValueError("persisted operations differ from the exact reviewed plan")
        # Read the same database using the GUI's actual read-only connection.
        engine = create_operator_read_engine(database_path)
        try:
            with Session(engine, autoflush=False) as session:
                store = CeqaStore(session)
                for expected in bridge.preview.ceqa_records:
                    actual = store.get(expected.ceqa_key)
                    if actual is None or actual.title != expected.title or (
                        actual.provenance[0].raw_reference
                        != expected.provenance[0].raw_reference
                    ):
                        raise ValueError("operator could not retrieve the exact imported source")
        finally:
            engine.dispose()
    except (AuthorizationDeniedError, OSError, RuntimeError, ValueError) as exc:
        typer.echo(f"Reviewed CEQAnet import blocked or not fully verified: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                **_summary(bridge),
                "persistence_mutated": True,
                "applied_operations": result.execution.applied_count,
                "operator_readback_verified": True,
                "source_review_state": "unassessed",
                "commercial_leads_created": False,
                "operator_command": (
                    f"constructionsight-operator --database {database_path} --open-browser"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
