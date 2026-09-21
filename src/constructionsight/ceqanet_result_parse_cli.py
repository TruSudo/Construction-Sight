"""Command-line parser for stored CEQAnet result-page snapshots.

This CLI reads existing CEQAnet execution JSON or raw HTML and parses candidate
search-result records. It does not execute network requests, download documents,
or mutate persistence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters.ceqanet_result_parser import parse_ceqanet_result_page
from constructionsight.storage.runtime_artifacts import read_runtime_text

InputFormat = Literal["auto", "execution-json", "html"]
_INPUT_FORMATS = frozenset({"auto", "execution-json", "html"})

app = typer.Typer(help="Parse stored CEQAnet search-result pages.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Parse stored CEQAnet search-result pages."""


def _validated_input_format(value: str) -> InputFormat:
    """Validate the Typer-facing string while retaining a precise internal type."""

    normalized = value.strip().casefold()
    if normalized not in _INPUT_FORMATS:
        raise typer.BadParameter("input-format must be auto, execution-json, or html.")
    return cast(InputFormat, normalized)


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_json_object(
    input_path: Path, *, content: str | None = None,
) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        payload = json.loads(read_runtime_text(input_path) if content is None else content)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{input_path} is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _detect_input_format(
    input_path: Path, input_format: InputFormat, *, content: str | None = None,
) -> InputFormat:
    """Resolve auto input format without executing network requests."""

    if input_format != "auto":
        return input_format

    try:
        payload = json.loads(read_runtime_text(input_path) if content is None else content)
    except json.JSONDecodeError:
        return "html"

    if isinstance(payload, dict) and isinstance(payload.get("snapshots"), list):
        return "execution-json"
    return "html"


def _extract_html_from_execution_json(
    input_path: Path,
    *,
    snapshot_index: int,
    content: str | None = None,
) -> tuple[str, str | None, dict[str, Any]]:
    """Extract stored response HTML and source URL from execution JSON."""

    payload = _load_json_object(input_path, content=content)
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise typer.BadParameter("Execution JSON must contain a non-empty snapshots list.")

    if snapshot_index < 0 or snapshot_index >= len(snapshots):
        raise typer.BadParameter(
            f"snapshot-index must be between 0 and {len(snapshots) - 1}."
        )

    snapshot = snapshots[snapshot_index]
    if not isinstance(snapshot, dict):
        raise typer.BadParameter("Selected snapshot must be a JSON object.")

    body_text = snapshot.get("body_text")
    if not isinstance(body_text, str):
        raise typer.BadParameter("Selected snapshot must contain string body_text.")

    final_url = snapshot.get("final_url")
    request_url = snapshot.get("request_url")
    source_url = final_url if isinstance(final_url, str) else request_url

    input_metadata = {
        "input_format": "execution-json",
        "snapshot_index": snapshot_index,
        "snapshot": {
            "page_number": snapshot.get("page_number"),
            "request_url": request_url,
            "final_url": final_url,
            "status_code": snapshot.get("status_code"),
            "content_type": snapshot.get("content_type"),
            "body_length": snapshot.get("body_length"),
            "body_truncated": snapshot.get("body_truncated"),
            "executed": snapshot.get("executed"),
            "reachable": snapshot.get("reachable"),
        },
    }
    return body_text, source_url if isinstance(source_url, str) else None, input_metadata


def _extract_html(
    input_path: Path,
    *,
    input_format: InputFormat,
    snapshot_index: int,
) -> tuple[str, str | None, dict[str, Any]]:
    """Extract HTML from raw HTML input or CEQAnet listing-execution JSON."""

    content = read_runtime_text(input_path)
    resolved_format = _detect_input_format(input_path, input_format, content=content)
    if resolved_format == "execution-json":
        return _extract_html_from_execution_json(
            input_path, snapshot_index=snapshot_index, content=content,
        )

    return content, None, {
        "input_format": "html",
        "snapshot_index": None,
        "snapshot": None,
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
        typer.echo(f"Wrote CEQAnet result parse JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact result-parse summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    input_metadata = cast(dict[str, object], metadata["input"])

    summary = Table(title="CEQAnet Result Page Parse")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Schema", str(metadata["schema_version"]))
    summary.add_row("Input format", str(input_metadata["input_format"]))
    summary.add_row("Records", str(metadata["record_count"]))
    summary.add_row(
        "Detail enrichment required",
        str(metadata["detail_enrichment_required_count"]),
    )
    summary.add_row("Candidate blocks", str(metadata["candidate_block_count"]))
    summary.add_row("Candidate links", str(metadata["candidate_link_count"]))
    console.print(summary)

    records = cast(list[dict[str, object]], payload["records"])
    if records:
        table = Table(title="Parsed Records")
        table.add_column("Title")
        table.add_column("Title Source")
        table.add_column("Needs Detail")
        table.add_column("SCH")
        table.add_column("Lead Agency")
        table.add_column("County")
        table.add_column("URL")
        for record in records:
            table.add_row(
                str(record.get("title") or ""),
                str(record.get("title_source") or ""),
                str(record.get("requires_detail_enrichment") or False),
                str(record.get("sch_number") or ""),
                str(record.get("lead_agency") or ""),
                str(record.get("county") or ""),
                str(record.get("detail_url") or ""),
            )
        console.print(table)


@app.command("parse")
def parse_ceqanet_results(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet execution JSON or raw result-page HTML file.",
        ),
    ],
    input_format: Annotated[
        str,
        typer.Option("--input-format", help="Input format: auto, execution-json, or html."),
    ] = "auto",
    snapshot_index: Annotated[
        int,
        typer.Option(help="Snapshot index when reading CEQAnet execution JSON."),
    ] = 0,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Parse candidate CEQAnet result records from stored public HTML."""

    _reject_output_without_json(output_path, json_output)
    html, source_url, input_metadata = _extract_html(
        input_path,
        input_format=_validated_input_format(input_format),
        snapshot_index=snapshot_index,
    )
    report = parse_ceqanet_result_page(html, source_url=source_url)
    payload = report.to_dict()
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = input_metadata

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
