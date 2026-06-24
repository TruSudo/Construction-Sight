"""Offline CEQAnet chain report CLI.

This CLI composes already stored CEQAnet snapshots into one deterministic report:
listing execution JSON -> result parse -> detail execution JSON parses -> enrichment.
It performs no network requests, document downloads, or persistence mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters.ceqanet_detail_enrichment import enrich_ceqanet_result_records
from constructionsight.adapters.ceqanet_detail_parser import parse_ceqanet_detail_page
from constructionsight.adapters.ceqanet_result_parser import parse_ceqanet_result_page

app = typer.Typer(help="Build offline CEQAnet chain reports from stored snapshots.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Build offline CEQAnet chain reports from stored snapshots."""


def _reject_output_without_json(output_path: Path | None, json_output: bool) -> None:
    """Reject file output without machine-readable JSON output."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)


def _load_json_object(input_path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{input_path} is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _snapshot_from_execution_json(
    input_path: Path,
    *,
    snapshot_index: int,
) -> dict[str, Any]:
    """Return one snapshot object from stored execution JSON."""

    payload = _load_json_object(input_path)
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        raise typer.BadParameter(f"{input_path} must contain a non-empty snapshots list.")
    if snapshot_index < 0 or snapshot_index >= len(snapshots):
        raise typer.BadParameter(
            f"snapshot-index must be between 0 and {len(snapshots) - 1} for {input_path}."
        )
    snapshot = snapshots[snapshot_index]
    if not isinstance(snapshot, dict):
        raise typer.BadParameter(f"{input_path} snapshots[{snapshot_index}] must be a JSON object.")
    return cast(dict[str, Any], snapshot)


def _html_and_source_from_snapshot(snapshot: dict[str, Any], *, input_path: Path) -> tuple[str, str | None]:
    """Extract stored HTML and source URL from one execution snapshot."""

    body_text = snapshot.get("body_text")
    if not isinstance(body_text, str):
        raise typer.BadParameter(f"{input_path} selected snapshot must contain string body_text.")

    final_url = snapshot.get("final_url")
    request_url = snapshot.get("request_url")
    source_url = final_url if isinstance(final_url, str) else request_url
    return body_text, source_url if isinstance(source_url, str) else None


def _snapshot_summary(snapshot: dict[str, Any]) -> dict[str, object]:
    """Return stable snapshot metadata for chain report input audit."""

    return {
        "request_url": snapshot.get("request_url"),
        "final_url": snapshot.get("final_url"),
        "status_code": snapshot.get("status_code"),
        "content_type": snapshot.get("content_type"),
        "body_length": snapshot.get("body_length"),
        "body_truncated": snapshot.get("body_truncated"),
        "executed": snapshot.get("executed"),
        "reachable": snapshot.get("reachable"),
    }


def _parse_listing_execution(
    input_path: Path,
    *,
    snapshot_index: int,
) -> dict[str, object]:
    """Parse stored listing execution JSON into result-parse JSON."""

    snapshot = _snapshot_from_execution_json(input_path, snapshot_index=snapshot_index)
    html, source_url = _html_and_source_from_snapshot(snapshot, input_path=input_path)
    report = parse_ceqanet_result_page(html, source_url=source_url)
    payload = report.to_dict()
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {
        "path": str(input_path),
        "snapshot_index": snapshot_index,
        "snapshot": _snapshot_summary(snapshot),
    }
    return payload


def _parse_detail_execution(input_path: Path) -> dict[str, object]:
    """Parse one stored detail execution JSON into detail-parse JSON."""

    snapshot = _snapshot_from_execution_json(input_path, snapshot_index=0)
    html, source_url = _html_and_source_from_snapshot(snapshot, input_path=input_path)
    report = parse_ceqanet_detail_page(html, source_url=source_url)
    payload = report.to_dict()
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {
        "path": str(input_path),
        "snapshot_index": 0,
        "snapshot": _snapshot_summary(snapshot),
    }
    return payload


def _records_from_result_parse(result_parse: dict[str, object]) -> list[dict[str, Any]]:
    """Return JSON object result records from a result-parse payload."""

    records = result_parse.get("records")
    if not isinstance(records, list):
        raise typer.BadParameter("Result parse did not produce a records list.")

    typed_records: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise typer.BadParameter(f"Result parse records[{index}] must be a JSON object.")
        typed_records.append(cast(dict[str, Any], record))
    return typed_records


def _detail_parse_summary(detail_parse: dict[str, object]) -> dict[str, object]:
    """Return compact detail parse metadata for chain report output."""

    metadata = cast(dict[str, object], detail_parse.get("metadata") or {})
    detail = cast(dict[str, object], detail_parse.get("detail") or {})
    return {
        "source_url": metadata.get("source_url"),
        "has_human_title": metadata.get("has_human_title"),
        "label_count": metadata.get("label_count"),
        "link_count": metadata.get("link_count"),
        "title": detail.get("title"),
        "sch_number": detail.get("sch_number"),
        "title_source": detail.get("title_source"),
    }


def _build_chain_report(
    *,
    listing_execution_path: Path,
    detail_execution_paths: list[Path],
    listing_snapshot_index: int,
) -> dict[str, object]:
    """Build one offline CEQAnet chain report."""

    result_parse = _parse_listing_execution(
        listing_execution_path,
        snapshot_index=listing_snapshot_index,
    )
    detail_parses = [_parse_detail_execution(path) for path in detail_execution_paths]
    result_records = _records_from_result_parse(result_parse)
    enrichment_report = enrich_ceqanet_result_records(
        result_records,
        [cast(dict[str, Any], detail_parse) for detail_parse in detail_parses],
    ).to_dict()
    enrichment_metadata = cast(dict[str, object], enrichment_report["metadata"])
    result_metadata = cast(dict[str, object], result_parse["metadata"])

    return {
        "metadata": {
            "schema_version": "ceqanet_chain_report.v1",
            "listing_execution_path": str(listing_execution_path),
            "listing_snapshot_index": listing_snapshot_index,
            "detail_execution_paths": [str(path) for path in detail_execution_paths],
            "detail_execution_count": len(detail_execution_paths),
            "result_record_count": result_metadata.get("record_count"),
            "detail_parse_count": len(detail_parses),
            "enriched_count": enrichment_metadata.get("enriched_count"),
            "missing_detail_count": enrichment_metadata.get("missing_detail_count"),
            "sch_mismatch_count": enrichment_metadata.get("sch_mismatch_count"),
            "network_executed": False,
            "persistence_mutated": False,
        },
        "result_parse": result_parse,
        "detail_parse_summaries": [_detail_parse_summary(detail_parse) for detail_parse in detail_parses],
        "enrichment": enrichment_report,
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
        typer.echo(f"Wrote CEQAnet chain report JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, object]) -> None:
    """Render a compact chain report summary."""

    metadata = cast(dict[str, object], payload["metadata"])
    table = Table(title="CEQAnet Chain Report")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "schema_version",
        "result_record_count",
        "detail_parse_count",
        "enriched_count",
        "missing_detail_count",
        "sch_mismatch_count",
        "network_executed",
        "persistence_mutated",
    ):
        table.add_row(field_name, str(metadata.get(field_name)))
    console.print(table)


@app.command("build")
def build_ceqanet_chain_report(
    listing_execution_path: Annotated[
        Path,
        typer.Option(
            "--listing-execution",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Stored CEQAnet listing execution JSON.",
        ),
    ],
    detail_execution_paths: Annotated[
        list[Path] | None,
        typer.Option(
            "--detail-execution",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Stored CEQAnet detail execution JSON. May be supplied multiple times.",
        ),
    ] = None,
    listing_snapshot_index: Annotated[
        int,
        typer.Option(help="Snapshot index to parse from listing execution JSON."),
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
    """Build a CEQAnet chain report from stored snapshots only."""

    _reject_output_without_json(output_path, json_output)
    detail_paths = detail_execution_paths or []
    payload = _build_chain_report(
        listing_execution_path=listing_execution_path,
        detail_execution_paths=detail_paths,
        listing_snapshot_index=listing_snapshot_index,
    )

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
