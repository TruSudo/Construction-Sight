"""Command-line enrichment for stored CEQAnet result/detail parse JSON.

This CLI reads existing CEQAnet result-parse JSON and existing CEQAnet
detail-parse JSON files, then emits a deterministic enrichment report. It does
not execute network requests, download documents, or mutate persistence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters.ceqanet_detail_enrichment import (
    enrich_ceqanet_result_records,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text

app = typer.Typer(help="Enrich stored CEQAnet result parses with stored detail parses.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Enrich stored CEQAnet result parses with stored detail parses."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_json_object(input_path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        payload = json.loads(read_runtime_text(input_path))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{input_path} is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _result_records_from_payload(payload: dict[str, Any], input_path: Path) -> list[dict[str, Any]]:
    """Return parsed CEQAnet result records from result-parse JSON."""

    records = payload.get("records")
    if not isinstance(records, list):
        raise typer.BadParameter(f"{input_path} must contain a records list.")

    result_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise typer.BadParameter(f"{input_path} records[{index}] must be a JSON object.")
        result_records.append(cast(dict[str, Any], record))
    return result_records


def _load_result_records(result_parse_path: Path) -> list[dict[str, Any]]:
    """Load CEQAnet result records from result-parse JSON."""

    return _result_records_from_payload(_load_json_object(result_parse_path), result_parse_path)


def _load_detail_parses(detail_parse_paths: list[Path]) -> list[dict[str, Any]]:
    """Load CEQAnet detail parse JSON objects."""

    detail_parses: list[dict[str, Any]] = []
    for detail_parse_path in detail_parse_paths:
        detail_parses.append(_load_json_object(detail_parse_path))
    return detail_parses


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
        typer.echo(f"Wrote CEQAnet detail enrichment JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact enrichment summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    input_metadata = cast(dict[str, object], metadata["input"])

    summary = Table(title="CEQAnet Detail Enrichment")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Schema", str(metadata["schema_version"]))
    summary.add_row("Result parse", str(input_metadata["result_parse_path"]))
    summary.add_row("Detail parses", str(input_metadata["detail_parse_count"]))
    summary.add_row("Records", str(metadata["record_count"]))
    summary.add_row("Enriched", str(metadata["enriched_count"]))
    summary.add_row("Missing detail", str(metadata["missing_detail_count"]))
    summary.add_row("SCH mismatch", str(metadata["sch_mismatch_count"]))
    console.print(summary)

    records = cast(list[dict[str, object]], payload["records"])
    if records:
        table = Table(title="Enriched Records")
        table.add_column("Status")
        table.add_column("Title")
        table.add_column("SCH")
        table.add_column("Title Source")
        table.add_column("Needs Detail")
        table.add_column("County")
        table.add_column("Detail URL")
        for record in records:
            table.add_row(
                str(record.get("enrichment_status") or ""),
                str(record.get("title") or ""),
                str(record.get("sch_number") or ""),
                str(record.get("title_source") or ""),
                str(record.get("requires_detail_enrichment") or False),
                str(record.get("county") or ""),
                str(record.get("detail_url") or ""),
            )
        console.print(table)


@app.command("enrich")
def enrich_ceqanet_details(
    result_parse_path: Annotated[
        Path,
        typer.Option(
            "--result-parse",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet result-parse JSON file.",
        ),
    ],
    detail_parse_paths: Annotated[
        list[Path] | None,
        typer.Option(
            "--detail-parse",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet detail-parse JSON file. May be supplied multiple times.",
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Enrich CEQAnet result records from stored parse JSON only."""

    _reject_output_without_json(output_path, json_output)

    resolved_detail_parse_paths = detail_parse_paths or []
    result_records = _load_result_records(result_parse_path)
    detail_parses = _load_detail_parses(resolved_detail_parse_paths)

    report = enrich_ceqanet_result_records(result_records, detail_parses)
    payload = report.to_dict()
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {
        "result_parse_path": str(result_parse_path),
        "detail_parse_paths": [str(path) for path in resolved_detail_parse_paths],
        "detail_parse_count": len(resolved_detail_parse_paths),
    }

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
