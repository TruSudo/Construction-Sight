"""Guarded CLI for fetching one CEQAnet detail/project page snapshot.

This command requires explicit operator consent before live network execution.
It fetches one public CEQAnet HTML page into deterministic execution JSON. It
does not download documents, parse records, or mutate persistence.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import httpx
import typer
from rich.console import Console
from rich.table import Table

from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access

app = typer.Typer(help="Execute guarded CEQAnet detail/project page fetches.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Execute guarded CEQAnet detail/project page fetches."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _validate_ceqanet_url(url: str) -> str:
    """Validate that a URL targets the public CEQAnet host."""

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("--url must be an HTTP(S) URL.")
    if parsed.netloc.lower() != "ceqanet.lci.ca.gov":
        raise ValueError("--url must target ceqanet.lci.ca.gov.")
    if not parsed.path or parsed.path == "/":
        raise ValueError("--url must identify a CEQAnet detail/project path.")
    return url


def _execute_detail_request(
    url: str,
    *,
    timeout_seconds: float,
    max_body_chars: int,
) -> dict[str, object]:
    """Fetch one public CEQAnet URL and return a bounded response snapshot."""

    try:
        response = httpx.get(
            url,
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": "ConstructionSight/0.1"},
        )
    except httpx.HTTPError as exc:
        return {
            "method": "GET",
            "request_url": url,
            "final_url": url,
            "status_code": None,
            "content_type": None,
            "body_text": "",
            "body_length": 0,
            "body_truncated": False,
            "executed": True,
            "error": exc.__class__.__name__,
            "reachable": False,
        }

    body_text = response.text
    body_length = len(body_text)
    headers: Mapping[str, str] = response.headers
    return {
        "method": "GET",
        "request_url": url,
        "final_url": str(response.url),
        "status_code": response.status_code,
        "content_type": headers.get("content-type"),
        "body_text": body_text[:max_body_chars],
        "body_length": body_length,
        "body_truncated": body_length > max_body_chars,
        "executed": True,
        "error": None,
        "reachable": 200 <= response.status_code < 400,
    }


def _report_to_dict(
    *,
    url: str,
    access_decision: AccessDecision,
    access_reason: str,
    snapshots: list[dict[str, object]],
) -> dict[str, object]:
    """Build deterministic CEQAnet detail execution JSON."""

    successful_count = sum(1 for snapshot in snapshots if snapshot.get("reachable") is True)
    return {
        "metadata": {
            "schema_version": "ceqanet_detail_execution.v1",
            "allowed": access_decision is AccessDecision.ALLOWED,
            "reason": (
                "CEQAnet detail executor completed bounded read-only GET request."
                if snapshots
                else access_reason
            ),
            "planned_request_count": 1,
            "executed_request_count": len(snapshots),
            "successful_response_count": successful_count,
            "failed_response_count": len(snapshots) - successful_count,
            "access": {
                "decision": access_decision.value,
                "reason": access_reason,
            },
            "requested_url": url,
        },
        "snapshots": snapshots,
    }


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _write_or_print_json(payload: dict[str, object], output_path: Path | None) -> None:
    """Write JSON to a file or print it to stdout."""

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet detail execution JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_report(payload: dict[str, object]) -> None:
    """Render a CEQAnet detail execution report as Rich tables."""

    metadata = payload["metadata"]
    assert isinstance(metadata, dict)

    summary = Table(title="CEQAnet Detail Execution")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Schema", str(metadata["schema_version"]))
    summary.add_row("Allowed", str(metadata["allowed"]))
    summary.add_row("Reason", str(metadata["reason"]))
    summary.add_row("Requested URL", str(metadata["requested_url"]))
    summary.add_row("Executed requests", str(metadata["executed_request_count"]))
    summary.add_row("Successful responses", str(metadata["successful_response_count"]))
    summary.add_row("Failed responses", str(metadata["failed_response_count"]))
    console.print(summary)

    snapshots = payload["snapshots"]
    assert isinstance(snapshots, list)
    table = Table(title="Bounded Detail Snapshot")
    table.add_column("Status")
    table.add_column("Reachable")
    table.add_column("Truncated")
    table.add_column("Body Length")
    table.add_column("Final URL")
    for snapshot in snapshots:
        assert isinstance(snapshot, dict)
        table.add_row(
            str(snapshot.get("status_code")),
            str(snapshot.get("reachable")),
            str(snapshot.get("body_truncated")),
            str(snapshot.get("body_length")),
            str(snapshot.get("final_url")),
        )
    console.print(table)


@app.command("execute")
def execute_ceqanet_detail(
    detail_url: Annotated[
        str,
        typer.Option("--url", help="Public CEQAnet detail/project URL to fetch."),
    ],
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
        typer.Option(help="Maximum response body characters retained in the snapshot."),
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
    """Execute one bounded CEQAnet detail/project GET request after explicit consent."""

    _reject_output_without_json(output_path, json_output)
    if timeout_seconds <= 0:
        raise typer.BadParameter("timeout-seconds must be greater than 0.")
    if max_body_chars < 1:
        raise typer.BadParameter("max-body-chars must be at least 1.")
    if not execute_live:
        typer.echo("Refusing live execution without --execute-live.")
        raise typer.Exit(code=1)

    try:
        resolved_url = _validate_ceqanet_url(detail_url)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

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

    snapshots: list[dict[str, object]] = []
    if access_result.decision is AccessDecision.ALLOWED:
        snapshots.append(
            _execute_detail_request(
                resolved_url,
                timeout_seconds=timeout_seconds,
                max_body_chars=max_body_chars,
            )
        )

    payload = _report_to_dict(
        url=resolved_url,
        access_decision=access_result.decision,
        access_reason=access_result.reason,
        snapshots=snapshots,
    )

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_report(payload)
