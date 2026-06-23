"""Guarded CLI for executing bounded CEQAnet read-only listing plans.

This command is intentionally separate from the planning CLI. It requires an
explicit operator consent flag before it can execute network requests. It does
not submit forms, download documents, parse records, or persist data.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingPlan,
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_executor import (
    CeqanetListingExecutionReport,
    CeqanetListingReadOnlyExecutor,
    CeqanetListingResponseSnapshot,
)
from constructionsight.legal import SourceAccessProfile, evaluate_access

app = typer.Typer(help="Execute guarded CEQAnet read-only listing plans.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Execute guarded CEQAnet read-only listing plans."""


def _normalize_options(values: list[str] | None) -> tuple[str, ...]:
    """Convert repeated CLI options into an immutable tuple."""

    if values is None:
        return ()
    return tuple(value for value in values if value.strip())


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    """Parse an optional ISO-8601 date string."""

    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{field_name} must be an ISO date, e.g. 2026-01-31.") from exc


def _build_query(
    *,
    county: list[str] | None,
    document_type: list[str] | None,
    lead_agency: list[str] | None,
    text: list[str] | None,
    received_from: str | None,
    received_to: str | None,
    posted_from: str | None,
    posted_to: str | None,
    high_signal_only: bool,
    page_size: int,
    max_pages: int,
) -> CeqanetListingQuery:
    """Build a validated CEQAnet listing query from CLI values."""

    try:
        return CeqanetListingQuery(
            counties=_normalize_options(county),
            document_types=_normalize_options(document_type),
            lead_agencies=_normalize_options(lead_agency),
            text_terms=_normalize_options(text),
            received_from=_parse_optional_date(received_from, "received-from"),
            received_to=_parse_optional_date(received_to, "received-to"),
            posted_from=_parse_optional_date(posted_from, "posted-from"),
            posted_to=_parse_optional_date(posted_to, "posted-to"),
            high_signal_only=high_signal_only,
            page_size=page_size,
            max_pages=max_pages,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _build_plan(
    *,
    query: CeqanetListingQuery,
    public_url: str,
    requires_login: bool,
    has_captcha: bool,
    robots_disallows_collection: bool,
    terms_disallow_collection: bool,
    paywalled: bool,
) -> CeqanetListingPlan:
    """Build an access-gated CEQAnet listing plan from CLI values."""

    access_result = evaluate_access(
        SourceAccessProfile(
            public_url=public_url,
            requires_login=requires_login,
            has_captcha=has_captcha,
            robots_disallows_collection=robots_disallows_collection,
            terms_disallow_collection=terms_disallow_collection,
            paywalled=paywalled,
        )
    )
    return CeqanetReadOnlyListingPlanner().build_plan(query, access_result)


def _query_to_dict(query: CeqanetListingQuery) -> dict[str, Any]:
    """Convert a CEQAnet listing query into JSON-safe output."""

    return {
        "counties": list(query.counties),
        "document_types": list(query.document_types),
        "lead_agencies": list(query.lead_agencies),
        "text_terms": list(query.text_terms),
        "received_from": query.received_from.isoformat() if query.received_from else None,
        "received_to": query.received_to.isoformat() if query.received_to else None,
        "posted_from": query.posted_from.isoformat() if query.posted_from else None,
        "posted_to": query.posted_to.isoformat() if query.posted_to else None,
        "high_signal_only": query.high_signal_only,
        "page_size": query.page_size,
        "max_pages": query.max_pages,
    }


def _snapshot_to_dict(snapshot: CeqanetListingResponseSnapshot) -> dict[str, Any]:
    """Convert one response snapshot into JSON-safe output."""

    return {
        "page_number": snapshot.page_number,
        "method": snapshot.method,
        "request_url": snapshot.request_url,
        "final_url": snapshot.final_url,
        "status_code": snapshot.status_code,
        "content_type": snapshot.content_type,
        "body_text": snapshot.body_text,
        "body_length": snapshot.body_length,
        "body_truncated": snapshot.body_truncated,
        "executed": snapshot.executed,
        "error": snapshot.error,
        "reachable": snapshot.reachable,
    }


def _report_to_dict(
    report: CeqanetListingExecutionReport,
    plan: CeqanetListingPlan,
) -> dict[str, Any]:
    """Convert an execution report into deterministic JSON-safe output."""

    return {
        "metadata": {
            "schema_version": "ceqanet_listing_execution.v1",
            "allowed": report.allowed,
            "reason": report.reason,
            "planned_request_count": report.planned_request_count,
            "executed_request_count": report.executed_request_count,
            "successful_response_count": report.successful_response_count,
            "failed_response_count": report.failed_response_count,
            "maximum_records": report.maximum_records,
            "access": {
                "decision": plan.access_result.decision.value,
                "reason": plan.access_result.reason,
            },
            "query": _query_to_dict(plan.query),
        },
        "snapshots": [_snapshot_to_dict(snapshot) for snapshot in report.snapshots],
    }


def _write_json_file(output_path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _write_or_print_json(payload: dict[str, Any], output_path: Path | None) -> None:
    """Write JSON to a file or print it to stdout."""

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet listing execution JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_report(report: CeqanetListingExecutionReport) -> None:
    """Render a CEQAnet listing execution report as Rich tables."""

    summary = Table(title="CEQAnet Listing Execution")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Allowed", str(report.allowed))
    summary.add_row("Reason", report.reason)
    summary.add_row("Planned requests", str(report.planned_request_count))
    summary.add_row("Executed requests", str(report.executed_request_count))
    summary.add_row("Successful responses", str(report.successful_response_count))
    summary.add_row("Failed responses", str(report.failed_response_count))
    summary.add_row("Maximum records", str(report.maximum_records))
    console.print(summary)

    snapshots = Table(title="Bounded Response Snapshots")
    snapshots.add_column("Page")
    snapshots.add_column("Status")
    snapshots.add_column("Reachable")
    snapshots.add_column("Truncated")
    snapshots.add_column("URL")
    for snapshot in report.snapshots:
        snapshots.add_row(
            str(snapshot.page_number),
            str(snapshot.status_code),
            str(snapshot.reachable),
            str(snapshot.body_truncated),
            snapshot.request_url,
        )
    console.print(snapshots)


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


@app.command("execute")
def execute_ceqanet_listing(
    county: Annotated[
        list[str] | None,
        typer.Option("--county", help="County filter. Repeat for multiple counties."),
    ] = None,
    document_type: Annotated[
        list[str] | None,
        typer.Option("--document-type", help="Document-type filter. Repeat for multiple types."),
    ] = None,
    lead_agency: Annotated[
        list[str] | None,
        typer.Option("--lead-agency", help="Lead-agency filter. Repeat for multiple agencies."),
    ] = None,
    text: Annotated[
        list[str] | None,
        typer.Option("--text", help="Required text term. Repeat for all required terms."),
    ] = None,
    received_from: Annotated[
        str | None,
        typer.Option(help="Inclusive received-date lower bound, ISO format YYYY-MM-DD."),
    ] = None,
    received_to: Annotated[
        str | None,
        typer.Option(help="Inclusive received-date upper bound, ISO format YYYY-MM-DD."),
    ] = None,
    posted_from: Annotated[
        str | None,
        typer.Option(help="Inclusive posted-date lower bound, ISO format YYYY-MM-DD."),
    ] = None,
    posted_to: Annotated[
        str | None,
        typer.Option(help="Inclusive posted-date upper bound, ISO format YYYY-MM-DD."),
    ] = None,
    high_signal_only: Annotated[
        bool,
        typer.Option(help="Plan only high-signal CEQA document-type listings."),
    ] = False,
    page_size: Annotated[int, typer.Option(help="Planned page size, capped at 100.")] = 25,
    max_pages: Annotated[int, typer.Option(help="Planned page count, capped at 10.")] = 1,
    public_url: Annotated[
        str,
        typer.Option(help="Public CEQAnet URL evaluated by access policy."),
    ] = "https://ceqanet.lci.ca.gov/",
    requires_login: Annotated[
        bool,
        typer.Option(help="Mark source as requiring login for access-policy preview."),
    ] = False,
    has_captcha: Annotated[
        bool,
        typer.Option(help="Mark source as presenting captcha for access-policy preview."),
    ] = False,
    robots_disallows_collection: Annotated[
        bool,
        typer.Option(help="Mark source as robots-disallowed for access-policy preview."),
    ] = False,
    terms_disallow_collection: Annotated[
        bool,
        typer.Option(help="Mark source terms as disallowing collection."),
    ] = False,
    paywalled: Annotated[
        bool,
        typer.Option(help="Mark source as paywalled for access-policy preview."),
    ] = False,
    timeout_seconds: Annotated[float, typer.Option(help="HTTP timeout in seconds.")] = 20.0,
    max_body_chars: Annotated[
        int,
        typer.Option(help="Maximum response body characters retained per snapshot."),
    ] = 50_000,
    execute_live: Annotated[
        bool,
        typer.Option("--execute-live", help="Required explicit consent for network execution."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of Rich tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Execute a bounded CEQAnet read-only listing plan after explicit consent."""

    _reject_output_without_json(output_path, json_output)
    if not execute_live:
        typer.echo("Refusing live execution without --execute-live.")
        raise typer.Exit(code=1)
    query = _build_query(
        county=county,
        document_type=document_type,
        lead_agency=lead_agency,
        text=text,
        received_from=received_from,
        received_to=received_to,
        posted_from=posted_from,
        posted_to=posted_to,
        high_signal_only=high_signal_only,
        page_size=page_size,
        max_pages=max_pages,
    )
    plan = _build_plan(
        query=query,
        public_url=public_url,
        requires_login=requires_login,
        has_captcha=has_captcha,
        robots_disallows_collection=robots_disallows_collection,
        terms_disallow_collection=terms_disallow_collection,
        paywalled=paywalled,
    )
    report = CeqanetListingReadOnlyExecutor(
        timeout_seconds=timeout_seconds,
        max_body_chars=max_body_chars,
    ).run(plan)

    if json_output:
        _write_or_print_json(_report_to_dict(report, plan), output_path)
        return
    _render_report(report)
