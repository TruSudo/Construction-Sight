"""Guarded CLI for one scope-bound CEQAnet listing plan execution."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingPlan,
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.ceqanet_listing_service import (
    CeqanetListingServiceError,
    execute_authorized_ceqanet_listing,
)
from constructionsight.legal import SourceAccessProfile, evaluate_access
from constructionsight.storage.runtime_artifacts import write_runtime_text

app = typer.Typer(help="Execute governed CEQAnet read-only listing plans.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Execute governed CEQAnet read-only listing plans."""


def _normalize_options(values: list[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(value for value in values if value.strip())


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(
            f"{field_name} must be an ISO date, e.g. 2026-01-31."
        ) from exc


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
    profile: SourceAccessProfile,
) -> CeqanetListingPlan:
    return CeqanetReadOnlyListingPlanner().build_plan(
        query,
        evaluate_access(profile),
    )


def _write_or_print_json(
    payload: dict[str, object],
    output_path: Path | None,
) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    if output_path is not None:
        write_runtime_text(output_path, rendered)
        typer.echo(f"Wrote CEQAnet listing execution JSON to {output_path}.")
        return
    typer.echo(rendered, nl=False)


def _render_report(payload: dict[str, object]) -> None:
    metadata = cast(dict[str, object], payload["metadata"])
    authorization = cast(dict[str, object], metadata["authorization"])
    summary = Table(title="CEQAnet Listing Execution")
    summary.add_column("Field")
    summary.add_column("Value")
    for field in (
        "allowed",
        "reason",
        "planned_request_count",
        "executed_request_count",
        "successful_response_count",
        "failed_response_count",
        "maximum_records",
        "plan_id",
    ):
        summary.add_row(field, str(metadata.get(field)))
    summary.add_row("operator", str(authorization.get("actor_id")))
    summary.add_row("decision", str(authorization.get("decision_id")))
    summary.add_row("preflight", str(authorization.get("preflight_id")))
    console.print(summary)

    snapshots = Table(title="Bounded Response Snapshots")
    for heading in (
        "Page",
        "Status",
        "Reachable",
        "Failure",
        "Truncated",
        "URL",
    ):
        snapshots.add_column(heading)
    for raw_snapshot in cast(list[dict[str, Any]], payload["snapshots"]):
        snapshots.add_row(
            str(raw_snapshot.get("page_number")),
            str(raw_snapshot.get("status_code")),
            str(raw_snapshot.get("reachable")),
            str(raw_snapshot.get("failure_kind")),
            str(raw_snapshot.get("body_truncated")),
            str(raw_snapshot.get("request_url")),
        )
    console.print(snapshots)


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
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
        typer.Option(
            "--document-type",
            help="Document-type filter. Repeat for multiple types.",
        ),
    ] = None,
    lead_agency: Annotated[
        list[str] | None,
        typer.Option(
            "--lead-agency",
            help="Lead-agency filter. Repeat for multiple agencies.",
        ),
    ] = None,
    text: Annotated[
        list[str] | None,
        typer.Option("--text", help="Unsupported until search contract verification."),
    ] = None,
    received_from: Annotated[
        str | None,
        typer.Option(help="Inclusive received-date lower bound, YYYY-MM-DD."),
    ] = None,
    received_to: Annotated[
        str | None,
        typer.Option(help="Inclusive received-date upper bound, YYYY-MM-DD."),
    ] = None,
    posted_from: Annotated[
        str | None,
        typer.Option(help="Inclusive posted-date lower bound, YYYY-MM-DD."),
    ] = None,
    posted_to: Annotated[
        str | None,
        typer.Option(help="Inclusive posted-date upper bound, YYYY-MM-DD."),
    ] = None,
    high_signal_only: Annotated[
        bool,
        typer.Option(help="Plan only high-signal CEQA document-type listings."),
    ] = False,
    page_size: Annotated[
        int,
        typer.Option(min=1, max=100, help="Planned page size."),
    ] = 25,
    max_pages: Annotated[
        int,
        typer.Option(min=1, max=10, help="Planned page count."),
    ] = 1,
    public_url: Annotated[
        str,
        typer.Option(help="Public CEQAnet URL evaluated by access policy."),
    ] = "https://ceqanet.lci.ca.gov/",
    access_fact_basis: Annotated[
        str | None,
        typer.Option(
            "--access-fact-basis",
            help="Retained evidence or reviewed-artifact identity for access facts.",
        ),
    ] = None,
    requires_login: Annotated[
        bool,
        typer.Option(help="Mark source as requiring login."),
    ] = False,
    has_captcha: Annotated[
        bool,
        typer.Option(help="Mark source as presenting captcha."),
    ] = False,
    robots_disallows_collection: Annotated[
        bool,
        typer.Option(help="Mark source as robots-disallowed."),
    ] = False,
    terms_disallow_collection: Annotated[
        bool,
        typer.Option(help="Mark source terms as disallowing collection."),
    ] = False,
    paywalled: Annotated[
        bool,
        typer.Option(help="Mark source as paywalled."),
    ] = False,
    timeout_seconds: Annotated[
        float,
        typer.Option(min=0.001, max=20.0, help="Read timeout in seconds."),
    ] = 20.0,
    max_body_bytes: Annotated[
        int,
        typer.Option(
            "--max-body-bytes",
            min=1,
            max=50_000,
            help="Maximum streamed response bytes retained per page.",
        ),
    ] = 50_000,
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help="Optional local audit identity; this is not authentication.",
        ),
    ] = None,
    authorization_reason: Annotated[
        str,
        typer.Option(
            "--authorization-reason",
            help="Reason for this exact listing-plan authorization.",
        ),
    ] = "Execute one reviewed CEQAnet listing plan.",
    execute_live: Annotated[
        bool,
        typer.Option(
            "--execute-live",
            help=(
                "Additional caller confirmation. This Boolean is not the operative "
                "authorization decision."
            ),
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON; requires --json-output."),
    ] = None,
) -> None:
    """Authorize and execute one bounded CEQAnet read-only listing plan."""

    if not execute_live:
        typer.echo(
            "Refusing live execution without --execute-live; caller confirmation is "
            "required in addition to scope-bound authority.",
            err=True,
        )
        raise typer.Exit(code=1)
    _reject_output_without_json(output_path, json_output)
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
    profile = SourceAccessProfile(
        public_url=public_url,
        access_fact_basis=access_fact_basis,
        requires_login=requires_login,
        has_captcha=has_captcha,
        robots_disallows_collection=robots_disallows_collection,
        terms_disallow_collection=terms_disallow_collection,
        paywalled=paywalled,
    )
    plan = _build_plan(query=query, profile=profile)
    try:
        payload = execute_authorized_ceqanet_listing(
            plan=plan,
            access_profile=profile,
            authorization_reason=authorization_reason,
            caller_confirmation=True,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_body_bytes,
            operator_id=operator_id,
        )
    except (
        AuthorizationDeniedError,
        CeqanetListingServiceError,
        ValueError,
    ) as exc:
        typer.echo(f"CEQAnet listing execution blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_report(payload)


if __name__ == "__main__":
    app()
