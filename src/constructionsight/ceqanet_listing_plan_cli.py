"""Command-line interface for previewing CEQAnet read-only listing plans.

This CLI does not execute network requests. It turns operator filters and access
facts into an auditable listing plan so future live listing remains bounded by
query scope and lawful-access preflight.
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
    CeqanetListingPagePlan,
    CeqanetListingPlan,
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.legal import SourceAccessProfile, evaluate_access

app = typer.Typer(help="Preview bounded CEQAnet read-only listing plans.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Preview bounded CEQAnet read-only listing plans."""


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


def _page_to_dict(page: CeqanetListingPagePlan) -> dict[str, Any]:
    """Convert one listing page plan into JSON-safe output."""

    return {
        "method": page.method,
        "search_url": page.search_url,
        "page_number": page.page_number,
        "page_size": page.page_size,
        "params": [{"name": name, "value": value} for name, value in page.params],
        "downloads_documents": page.downloads_documents,
        "mutates_remote_state": page.mutates_remote_state,
    }


def _plan_to_dict(plan: CeqanetListingPlan) -> dict[str, Any]:
    """Convert a listing plan into deterministic JSON-safe output."""

    return {
        "metadata": {
            "schema_version": "ceqanet_listing_plan.v1",
            "allowed": plan.allowed,
            "reason": plan.reason,
            "maximum_records": plan.maximum_records,
            "access": {
                "decision": plan.access_result.decision.value,
                "reason": plan.access_result.reason,
            },
            "query": {
                "counties": list(plan.query.counties),
                "document_types": list(plan.query.document_types),
                "lead_agencies": list(plan.query.lead_agencies),
                "text_terms": list(plan.query.text_terms),
                "received_from": plan.query.received_from.isoformat()
                if plan.query.received_from
                else None,
                "received_to": plan.query.received_to.isoformat()
                if plan.query.received_to
                else None,
                "posted_from": plan.query.posted_from.isoformat()
                if plan.query.posted_from
                else None,
                "posted_to": plan.query.posted_to.isoformat() if plan.query.posted_to else None,
                "high_signal_only": plan.query.high_signal_only,
                "page_size": plan.query.page_size,
                "max_pages": plan.query.max_pages,
            },
        },
        "pages": [_page_to_dict(page) for page in plan.pages],
    }


def _write_json_file(output_path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _render_plan(plan: CeqanetListingPlan) -> None:
    """Render a CEQAnet listing plan as Rich tables."""

    summary = Table(title="CEQAnet Read-Only Listing Plan")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Allowed", str(plan.allowed))
    summary.add_row("Access decision", plan.access_result.decision.value)
    summary.add_row("Reason", plan.reason)
    summary.add_row("Planned pages", str(len(plan.pages)))
    summary.add_row("Maximum records", str(plan.maximum_records))
    console.print(summary)

    pages = Table(title="Planned GET Requests")
    pages.add_column("Page")
    pages.add_column("Method")
    pages.add_column("Search URL")
    pages.add_column("Params")
    for page in plan.pages:
        pages.add_row(
            str(page.page_number),
            page.method,
            page.search_url,
            "&".join(f"{name}={value}" for name, value in page.params),
        )
    console.print(pages)


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


@app.command("plan")
def plan_ceqanet_listing(
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
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of Rich tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Preview a bounded, access-gated CEQAnet read-only listing plan."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
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
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, access_result)

    if json_output:
        payload = _plan_to_dict(plan)
        if output_path is not None:
            _write_json_file(output_path, payload)
            typer.echo(f"Wrote CEQAnet listing plan JSON to {output_path}.")
            return
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return

    _render_plan(plan)
