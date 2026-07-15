"""Guarded CLI for one scope-bound CEQAnet detail-page read."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.ceqanet_detail_service import execute_authorized_ceqanet_detail
from constructionsight.legal import SourceAccessProfile

app = typer.Typer(help="Execute governed CEQAnet detail/project page reads.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Execute governed CEQAnet detail/project page reads."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    if output_path is not None and not json_output:
        raise typer.BadParameter("--output requires --json-output")


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _write_or_print_json(
    payload: dict[str, object],
    output_path: Path | None,
) -> None:
    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet detail execution JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_report(payload: dict[str, object]) -> None:
    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    authorization = metadata.get("authorization")
    assert isinstance(authorization, dict)

    summary = Table(title="CEQAnet Detail Execution")
    summary.add_column("Field")
    summary.add_column("Value")
    for field_name in (
        "schema_version",
        "allowed",
        "reason",
        "requested_url",
        "executed_request_count",
        "successful_response_count",
        "failed_response_count",
    ):
        summary.add_row(field_name, str(metadata.get(field_name)))
    summary.add_row("operator", str(authorization.get("actor_id")))
    summary.add_row("decision", str(authorization.get("decision_id")))
    summary.add_row("preflight", str(authorization.get("preflight_id")))
    summary.add_row("valid until", str(authorization.get("valid_until")))
    console.print(summary)

    snapshots = payload["snapshots"]
    assert isinstance(snapshots, list)
    table = Table(title="Bounded Detail Snapshot")
    table.add_column("Status")
    table.add_column("Reachable")
    table.add_column("Failure")
    table.add_column("Truncated")
    table.add_column("Body Length")
    table.add_column("Attempts")
    table.add_column("Final URL")
    for snapshot in snapshots:
        assert isinstance(snapshot, dict)
        table.add_row(
            str(snapshot.get("status_code")),
            str(snapshot.get("reachable")),
            str(snapshot.get("failure_kind")),
            str(snapshot.get("body_truncated")),
            str(snapshot.get("body_length")),
            str(snapshot.get("attempt_count")),
            str(snapshot.get("final_url")),
        )
    console.print(table)


@app.command("execute")
def execute_ceqanet_detail(
    detail_url: Annotated[
        str,
        typer.Option("--url", help="Exact public CEQAnet detail/project HTTPS URL."),
    ],
    operator_id: Annotated[
        str,
        typer.Option(
            "--operator-id",
            help="Explicit local operator audit identity; this is not authentication.",
        ),
    ],
    authorization_reason: Annotated[
        str,
        typer.Option(
            "--authorization-reason",
            help="Nonblank reason for this exact one-request authorization.",
        ),
    ],
    public_url: Annotated[
        str,
        typer.Option(help="Public source URL evaluated by lawful-access policy."),
    ] = "https://ceqanet.lci.ca.gov/",
    requires_login: Annotated[
        bool,
        typer.Option(help="Mark the source as requiring login."),
    ] = False,
    has_captcha: Annotated[
        bool,
        typer.Option(help="Mark the source as presenting captcha."),
    ] = False,
    robots_disallows_collection: Annotated[
        bool,
        typer.Option(help="Mark the intended path as robots-disallowed."),
    ] = False,
    terms_disallow_collection: Annotated[
        bool,
        typer.Option(help="Mark source terms as disallowing collection."),
    ] = False,
    paywalled: Annotated[
        bool,
        typer.Option(help="Mark the source as paywalled."),
    ] = False,
    timeout_seconds: Annotated[
        float,
        typer.Option(min=0.001, max=20.0, help="Read timeout in seconds."),
    ] = 20.0,
    max_body_bytes: Annotated[
        int,
        typer.Option(
            min=1,
            max=50_000,
            help="Maximum response bytes retained by CS-NET-006.",
        ),
    ] = 50_000,
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
        typer.Option("--output", help="Write JSON to a file; requires --json-output."),
    ] = None,
) -> None:
    """Authorize and execute one exact bounded CEQAnet GET request."""

    _reject_output_without_json(output_path, json_output)
    profile = SourceAccessProfile(
        public_url=public_url,
        requires_login=requires_login,
        has_captcha=has_captcha,
        robots_disallows_collection=robots_disallows_collection,
        terms_disallow_collection=terms_disallow_collection,
        paywalled=paywalled,
    )
    try:
        payload = execute_authorized_ceqanet_detail(
            detail_url=detail_url,
            access_profile=profile,
            operator_id=operator_id,
            authorization_reason=authorization_reason,
            caller_confirmation=execute_live,
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
        )
    except (AuthorizationDeniedError, ValueError) as exc:
        typer.echo(f"CEQAnet detail execution blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_report(payload)
