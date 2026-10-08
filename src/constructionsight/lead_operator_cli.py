"""Consolidated operator CLI for persisted post-enrichment lead records."""

from __future__ import annotations

import json
from typing import Annotated, NoReturn

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.lead_operator_models import LeadOperatorRecordKind
from constructionsight.lead_operator_service import (
    LeadOperatorError,
    get_lead_operator_record,
    list_lead_operator_records,
    load_persisted_lead_workflow,
)
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_rules import LEAD_WORKFLOW_TRANSITION_RULES
from constructionsight.operator_services.lead_workflow_transition_service import (
    apply_authorized_lead_workflow_transition,
)
from constructionsight.outreach_preview_models import (
    OutreachChannel,
    OutreachContactReference,
)
from constructionsight.outreach_preview_service import (
    OutreachPreviewError,
    build_persisted_outreach_preview,
)
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)

app = typer.Typer(help="ConstructionSight persisted lead workflow operator tools.")
console = Console()


def _database_factory(database_url: str | None) -> sessionmaker[Session]:
    engine = create_database_engine(database_url)
    initialize_database(engine)
    return session_factory(engine)


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=2)


@app.callback()
def lead_operator_root() -> None:
    """Inspect persisted lead records and apply governed workflow transitions."""


@app.command("list")
def list_records(
    record_kind: Annotated[
        LeadOperatorRecordKind,
        typer.Argument(help="Persisted lead record family to list."),
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
        typer.Option(
            help="Exact indexed status filter when supported by the record kind."
        ),
    ] = None,
    base_candidate_id: Annotated[
        str | None,
        typer.Option(help="Exact base candidate identifier filter when supported."),
    ] = None,
    workflow_id: Annotated[
        str | None,
        typer.Option(help="Exact workflow identifier filter when supported."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    """List newest persisted records without mutating workflow state."""

    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            records = list_lead_operator_records(
                session,
                record_kind,
                limit=limit,
                status=status,
                base_candidate_id=base_candidate_id,
                workflow_id=workflow_id,
            )
    except LeadOperatorError as exc:
        _fail(str(exc))

    if json_output:
        console.print_json(json.dumps([record.to_dict() for record in records]))
        return
    table = Table(title=f"ConstructionSight Lead Records: {record_kind.value}")
    table.add_column("ID")
    table.add_column("Status")
    table.add_column("Candidate")
    table.add_column("Workflow")
    table.add_column("Score")
    table.add_column("Observed")
    for record in records:
        table.add_row(
            record.record_id,
            record.status or "",
            record.base_candidate_id or "",
            record.workflow_id or "",
            "" if record.lead_score is None else str(record.lead_score),
            record.observed_created_at or "",
        )
    console.print(table)


@app.command("detail")
def record_detail(
    record_kind: Annotated[
        LeadOperatorRecordKind,
        typer.Argument(help="Persisted lead record family."),
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
        typer.Option(
            "--json-output",
            help="Print the normalized record envelope as JSON.",
        ),
    ] = False,
) -> None:
    """Show one record and its complete preserved payload."""

    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            record = get_lead_operator_record(session, record_kind, record_id)
    except LeadOperatorError as exc:
        _fail(str(exc))
    if record is None:
        _fail(f"{record_kind.value} record not found: {record_id}")
    if json_output:
        console.print_json(json.dumps(record.to_dict()))
        return
    summary = Table(title=f"ConstructionSight Lead Record: {record_kind.value}")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Record ID", record.record_id)
    summary.add_row("Status", record.status or "")
    summary.add_row("Base candidate", record.base_candidate_id or "")
    summary.add_row("Workflow", record.workflow_id or "")
    summary.add_row("Package", record.package_id or "")
    score = "" if record.lead_score is None else str(record.lead_score)
    summary.add_row("Lead score", score)
    summary.add_row("Observed created", record.observed_created_at or "")
    summary.add_row("Observed updated", record.observed_updated_at or "")
    console.print(summary)
    console.print_json(json.dumps(record.payload))


@app.command("allowed-transitions")
def allowed_transitions(
    workflow_id: Annotated[
        str,
        typer.Argument(help="Persisted workflow identifier."),
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
    """Show matrix-valid next statuses for a persisted workflow."""

    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            workflow = load_persisted_lead_workflow(session, workflow_id)
    except ValueError as exc:
        _fail(str(exc))
    allowed = sorted(
        status.value for status in LEAD_WORKFLOW_TRANSITION_RULES[workflow.status]
    )
    payload = {
        "workflow_id": workflow.workflow_id,
        "current_status": workflow.status.value,
        "allowed_next_statuses": allowed,
        "final_status": not allowed,
    }
    if json_output:
        console.print_json(json.dumps(payload))
        return
    table = Table(title="ConstructionSight Lead Workflow Transitions")
    table.add_column("Workflow")
    table.add_column("Current")
    table.add_column("Allowed next statuses")
    table.add_row(
        workflow.workflow_id,
        workflow.status.value,
        ", ".join(allowed) or "none",
    )
    console.print(table)


@app.command("outreach-preview")
def outreach_preview(
    workflow_id: Annotated[
        str,
        typer.Argument(help="Persisted workflow identifier."),
    ],
    expected_current_status: Annotated[
        LeadWorkflowStatus,
        typer.Option(
            "--expected-current-status",
            help="Required stale-state guard for the reviewed workflow.",
        ),
    ],
    channel: Annotated[
        OutreachChannel,
        typer.Option("--channel", help="Operator-confirmed business contact channel."),
    ],
    destination: Annotated[
        str,
        typer.Option("--destination", help="Business contact destination to preview."),
    ],
    business_role: Annotated[
        str,
        typer.Option("--business-role", help="Business role associated with the contact."),
    ],
    source_name: Annotated[
        str,
        typer.Option("--source-name", help="Source that established the contact path."),
    ],
    source_reference: Annotated[
        str,
        typer.Option(
            "--source-reference",
            help="URL, record reference, or other provenance for the contact path.",
        ),
    ],
    subject: Annotated[
        str,
        typer.Option("--subject", help="Preview subject."),
    ],
    body: Annotated[
        str,
        typer.Option("--body", help="Preview body."),
    ],
    contact_review_basis: Annotated[
        str,
        typer.Option(
            "--contact-review-basis",
            help=(
                "Required operator review basis for treating the destination "
                "as a business contact path."
            ),
        ),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable preview JSON."),
    ] = False,
) -> None:
    """Build a governed outreach preview without sending or authorizing outreach."""

    factory = _database_factory(database_url)
    contact = OutreachContactReference(
        channel=channel,
        destination=destination,
        business_role=business_role,
        source_name=source_name,
        source_reference=source_reference,
        contact_review_basis=contact_review_basis,
    )
    try:
        with managed_session(factory) as session:
            preview = build_persisted_outreach_preview(
                session,
                workflow_id=workflow_id,
                expected_current_status=expected_current_status,
                contact=contact,
                subject=subject,
                body=body,
            )
    except OutreachPreviewError as exc:
        _fail(str(exc))

    if json_output:
        console.print_json(json.dumps(preview.to_dict()))
        return

    table = Table(title="ConstructionSight Outreach Preview")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Preview ID", preview.preview_id)
    table.add_row("Workflow", preview.workflow_id)
    table.add_row("Workflow status", preview.workflow_status)
    table.add_row("Channel", preview.contact.channel.value)
    table.add_row("Business role", preview.contact.business_role)
    table.add_row("Destination", preview.contact.destination)
    table.add_row("Human approval required", str(preview.requires_human_approval))
    table.add_row("External send authorized", str(preview.external_send_authorized))
    table.add_row("Send executed", str(preview.send_executed))
    table.add_row("Bid authorized", str(preview.bid_authorized))
    console.print(table)
    console.print(f"Subject: {preview.subject}")
    console.print(preview.body)


@app.command("transition")
def transition_workflow(
    workflow_id: Annotated[
        str,
        typer.Argument(help="Persisted workflow identifier."),
    ],
    next_status: Annotated[
        LeadWorkflowStatus,
        typer.Argument(help="Matrix-valid next workflow status."),
    ],
    expected_current_status: Annotated[
        LeadWorkflowStatus,
        typer.Option(
            "--expected-current-status",
            help=(
                "Required stale-state guard matching the currently reviewed "
                "workflow status."
            ),
        ),
    ],
    reason: Annotated[
        str,
        typer.Option(
            "--reason",
            help="Required audit reason for the status transition.",
        ),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL."),
    ] = None,
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help="Optional local audit identity; this is not authentication.",
        ),
    ] = None,
    apply_changes: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Explicitly confirm the exact persisted status transition.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    """Apply one explicit, matrix-valid, stale-state-protected status transition."""

    if not apply_changes:
        _fail("Explicit --apply authorization is required.")
    factory = _database_factory(database_url)
    try:
        with managed_session(factory) as session:
            result = apply_authorized_lead_workflow_transition(
                session,
                workflow_id=workflow_id,
                expected_current_status=expected_current_status,
                next_status=next_status,
                reason=reason,
                caller_confirmation=True,
                operator_id=operator_id,
            )
    except (AuthorizationDeniedError, ValueError) as exc:
        _fail(str(exc))
    report = result.report
    if json_output:
        console.print_json(json.dumps(report.to_dict()))
        return
    table = Table(title="ConstructionSight Lead Workflow Transition")
    table.add_column("Workflow")
    table.add_column("Previous")
    table.add_column("Current")
    table.add_column("Event")
    table.add_column("Reason")
    table.add_row(
        report.workflow_id,
        report.previous_status,
        report.current_status,
        report.event_id,
        report.reason,
    )
    console.print(table)
