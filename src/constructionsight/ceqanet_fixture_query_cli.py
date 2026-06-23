"""Command-line interface for querying CEQAnet fixture rows.

This CLI is intentionally fixture-backed. It does not perform live HTTP requests,
submit forms, download documents, or persist records. It gives operators a safe
query surface before Phase 6 moves toward conservative live read-only listing.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters.ceqanet import CeqanetFixtureParser
from constructionsight.adapters.ceqanet_query import (
    CeqanetFixtureQuery,
    CeqanetFixtureQueryResult,
    CeqanetFixtureQueryService,
)
from constructionsight.ceqa_models import CeqaRecord

app = typer.Typer(help="Query deterministic CEQAnet fixture rows.")
console = Console()


@app.callback()
def main() -> None:
    """Query deterministic CEQAnet fixture rows."""


def _read_fixture_rows(input_path: Path) -> list[dict[str, Any]]:
    """Read CEQAnet-like fixture rows from a JSON array file."""

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid CEQAnet fixture JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise typer.BadParameter("CEQAnet fixture JSON must be an array of row objects.")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise typer.BadParameter(f"CEQAnet fixture row {index} must be an object.")
        rows.append(item)
    return rows


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    """Parse an ISO-8601 date option when provided."""

    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{field_name} must be an ISO date, e.g. 2026-01-31.") from exc


def _normalize_options(values: list[str] | None) -> tuple[str, ...]:
    """Convert repeated CLI options into an immutable tuple."""

    if values is None:
        return ()
    return tuple(value for value in values if value.strip())


def _load_normalized_records(
    input_path: Path,
    *,
    source_name: str,
    source_url: str,
) -> list[CeqaRecord]:
    """Load fixture rows and normalize them through the CEQAnet parser contract."""

    parser = CeqanetFixtureParser()
    return [
        parser.parse_row(row, source_name=source_name, source_url=source_url)
        for row in _read_fixture_rows(input_path)
    ]


def _result_to_dict(result: CeqanetFixtureQueryResult) -> dict[str, Any]:
    """Convert a fixture query result into JSON-safe output."""

    return {
        "metadata": {
            "schema_version": "ceqanet_fixture_query.v1",
            "source_record_count": result.source_record_count,
            "matched_record_count": result.matched_record_count,
            "truncated": result.truncated,
            "query": {
                "counties": list(result.query.counties),
                "document_types": list(result.query.document_types),
                "lead_agencies": list(result.query.lead_agencies),
                "text_terms": list(result.query.text_terms),
                "received_from": result.query.received_from.isoformat()
                if result.query.received_from
                else None,
                "received_to": result.query.received_to.isoformat()
                if result.query.received_to
                else None,
                "posted_from": result.query.posted_from.isoformat()
                if result.query.posted_from
                else None,
                "posted_to": result.query.posted_to.isoformat() if result.query.posted_to else None,
                "high_signal_only": result.query.high_signal_only,
                "limit": result.query.limit,
            },
        },
        "records": [record.model_dump(mode="json") for record in result.records],
    }


def _write_json_file(output_path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic UTF-8 JSON output."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )


def _render_result(result: CeqanetFixtureQueryResult) -> None:
    """Render a CEQAnet fixture query result as Rich tables."""

    summary = Table(title="CEQAnet Fixture Query")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Source records", str(result.source_record_count))
    summary.add_row("Matched records", str(result.matched_record_count))
    summary.add_row("Truncated", str(result.truncated))
    summary.add_row("High signal only", str(result.query.high_signal_only))
    console.print(summary)

    records = Table(title="Matched CEQA Records")
    records.add_column("CEQA key")
    records.add_column("Title")
    records.add_column("County")
    records.add_column("Document")
    records.add_column("Lead agency")
    records.add_column("Received")
    for record in result.records:
        records.add_row(
            record.ceqa_key,
            record.title,
            record.county or "",
            record.document_type or "",
            record.lead_agency or "",
            record.received_date.isoformat() if record.received_date else "",
        )
    console.print(records)


@app.command("query")
def query_ceqanet_fixtures(
    input_path: Annotated[
        Path,
        typer.Argument(help="Path to a CEQAnet fixture JSON array file."),
    ],
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
        typer.Option(help="Return only high-signal CEQA document types."),
    ] = False,
    limit: Annotated[int | None, typer.Option(help="Maximum number of matched records.")] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of Rich tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
    source_name: Annotated[
        str,
        typer.Option(help="Source name used for normalized provenance."),
    ] = "CEQAnet Fixture Rows",
    source_url: Annotated[
        str,
        typer.Option(help="Source URL used when a row does not provide record_url."),
    ] = "https://ceqanet.lci.ca.gov/",
) -> None:
    """Query fixture-backed CEQAnet rows through normalized CEQA records."""

    if output_path is not None and not json_output:
        raise typer.BadParameter("--output requires --json-output.")
    query = CeqanetFixtureQuery(
        counties=_normalize_options(county),
        document_types=_normalize_options(document_type),
        lead_agencies=_normalize_options(lead_agency),
        text_terms=_normalize_options(text),
        received_from=_parse_optional_date(received_from, "received-from"),
        received_to=_parse_optional_date(received_to, "received-to"),
        posted_from=_parse_optional_date(posted_from, "posted-from"),
        posted_to=_parse_optional_date(posted_to, "posted-to"),
        high_signal_only=high_signal_only,
        limit=limit,
    )
    records = _load_normalized_records(input_path, source_name=source_name, source_url=source_url)
    result = CeqanetFixtureQueryService().query(records, query)

    if json_output:
        payload = _result_to_dict(result)
        if output_path is not None:
            _write_json_file(output_path, payload)
            typer.echo(f"Wrote CEQAnet fixture query JSON to {output_path}.")
            return
        console.print_json(json.dumps(payload))
        return

    _render_result(result)
