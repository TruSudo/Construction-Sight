"""Command-line export for CEQAnet advanced-search vocabulary snapshots.

This CLI reads an existing CEQAnet HTML snapshot or listing-execution JSON file,
extracts the public Advanced Search vocabulary, and emits deterministic JSON.
It does not execute network requests, download documents, parse result records,
or mutate persistence.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Annotated, Any, Literal, cast

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters.ceqanet_search_contract import CEQANET_FIELD_LEAD_AGENCY
from constructionsight.adapters.ceqanet_search_vocabulary import (
    CeqanetSearchVocabulary,
    CeqanetSearchVocabularyOption,
    classify_ceqanet_lead_agency,
    parse_ceqanet_search_vocabulary,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

InputFormat = Literal["auto", "execution-json", "html"]
_INPUT_FORMATS = frozenset({"auto", "execution-json", "html"})

app = typer.Typer(help="Export CEQAnet advanced-search controlled vocabulary.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Export CEQAnet advanced-search controlled vocabulary."""


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
) -> tuple[str, dict[str, Any]]:
    """Extract stored response HTML from CEQAnet listing-execution JSON."""

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

    snapshot_metadata = {
        "page_number": snapshot.get("page_number"),
        "request_url": snapshot.get("request_url"),
        "final_url": snapshot.get("final_url"),
        "status_code": snapshot.get("status_code"),
        "content_type": snapshot.get("content_type"),
        "body_length": snapshot.get("body_length"),
        "body_truncated": snapshot.get("body_truncated"),
        "executed": snapshot.get("executed"),
        "reachable": snapshot.get("reachable"),
    }
    input_metadata = {
        "input_format": "execution-json",
        "snapshot_index": snapshot_index,
        "snapshot": snapshot_metadata,
    }
    return body_text, input_metadata


def _extract_html(
    input_path: Path,
    *,
    input_format: InputFormat,
    snapshot_index: int,
) -> tuple[str, dict[str, Any]]:
    """Extract HTML from raw HTML input or CEQAnet listing-execution JSON."""

    content = read_runtime_text(input_path)
    resolved_format = _detect_input_format(input_path, input_format, content=content)
    if resolved_format == "execution-json":
        return _extract_html_from_execution_json(
            input_path, snapshot_index=snapshot_index, content=content,
        )

    return content, {
        "input_format": "html",
        "snapshot_index": None,
        "snapshot": None,
    }


def _option_to_dict(
    option: CeqanetSearchVocabularyOption,
    *,
    include_agency_types: bool,
) -> dict[str, str | bool]:
    """Convert one vocabulary option into deterministic JSON-safe output."""

    payload = option.to_dict()
    if (
        include_agency_types
        and option.field_name == CEQANET_FIELD_LEAD_AGENCY
        and option.value
    ):
        payload["agency_type"] = classify_ceqanet_lead_agency(option.label)
    return payload


def _agency_type_counts(vocabulary: CeqanetSearchVocabulary) -> dict[str, int]:
    """Count classified CEQAnet lead/public agency types."""

    try:
        lead_agencies = vocabulary.group(CEQANET_FIELD_LEAD_AGENCY).non_empty_options
    except KeyError:
        return {}

    counts = Counter(classify_ceqanet_lead_agency(option.label) for option in lead_agencies)
    return dict(sorted(counts.items()))


def _vocabulary_to_payload(
    vocabulary: CeqanetSearchVocabulary,
    *,
    input_path: Path,
    input_metadata: dict[str, Any],
    include_agency_types: bool,
) -> dict[str, Any]:
    """Convert extracted vocabulary into deterministic export JSON."""

    counts = {group.field_name: len(group.options) for group in vocabulary.groups}
    vocabulary_payload = {
        group.field_name: [
            _option_to_dict(option, include_agency_types=include_agency_types)
            for option in group.options
        ]
        for group in vocabulary.groups
    }
    metadata: dict[str, Any] = {
        "schema_version": "ceqanet_search_vocabulary.v1",
        "source_path": str(input_path),
        "input": input_metadata,
        "group_count": len(vocabulary.groups),
        "option_count": sum(counts.values()),
        "counts": counts,
        "includes_agency_types": include_agency_types,
    }
    if include_agency_types:
        metadata["lead_agency_type_counts"] = _agency_type_counts(vocabulary)

    return {
        "metadata": metadata,
        "vocabulary": vocabulary_payload,
    }


def _write_json_file(output_path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic UTF-8 JSON output."""
    write_runtime_text(
        output_path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


def _write_or_print_json(payload: dict[str, Any], output_path: Path | None) -> None:
    """Write JSON to a file or print it to stdout."""

    if output_path is not None:
        _write_json_file(output_path, payload)
        typer.echo(f"Wrote CEQAnet search vocabulary JSON to {output_path}.")
        return
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _render_summary(payload: dict[str, Any]) -> None:
    """Render a compact vocabulary summary table."""

    metadata = cast(dict[str, Any], payload["metadata"])
    counts = cast(dict[str, int], metadata["counts"])

    summary = Table(title="CEQAnet Search Vocabulary")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Schema", str(metadata["schema_version"]))
    input_metadata = cast(dict[str, Any], metadata["input"])
    summary.add_row("Input format", str(input_metadata["input_format"]))
    summary.add_row("Groups", str(metadata["group_count"]))
    summary.add_row("Options", str(metadata["option_count"]))
    console.print(summary)

    count_table = Table(title="Vocabulary Counts")
    count_table.add_column("Field")
    count_table.add_column("Options")
    for field_name, count in counts.items():
        count_table.add_row(field_name, str(count))
    console.print(count_table)

    agency_counts = metadata.get("lead_agency_type_counts")
    if isinstance(agency_counts, dict) and agency_counts:
        agency_table = Table(title="Lead/Public Agency Type Counts")
        agency_table.add_column("Agency Type")
        agency_table.add_column("Count")
        for agency_type, count in agency_counts.items():
            agency_table.add_row(str(agency_type), str(count))
        console.print(agency_table)


@app.command("export")
def export_ceqanet_vocabulary(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet execution JSON or raw Advanced Search HTML file.",
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
    include_agency_types: Annotated[
        bool,
        typer.Option(help="Classify LeadAgency options into practical source types."),
    ] = True,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write JSON output to a file. Requires --json-output."),
    ] = None,
) -> None:
    """Export CEQAnet advanced-search vocabulary from stored public HTML."""

    _reject_output_without_json(output_path, json_output)
    html, input_metadata = _extract_html(
        input_path,
        input_format=_validated_input_format(input_format),
        snapshot_index=snapshot_index,
    )
    vocabulary = parse_ceqanet_search_vocabulary(html)
    payload = _vocabulary_to_payload(
        vocabulary,
        input_path=input_path,
        input_metadata=input_metadata,
        include_agency_types=include_agency_types,
    )

    if json_output:
        _write_or_print_json(payload, output_path)
        return
    _render_summary(payload)
