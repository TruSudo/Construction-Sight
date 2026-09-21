"""Command-line CEQAnet operator report builder.

This CLI reads an existing CEQAnet operator package JSON and emits a deterministic
Markdown review report. It performs no network requests, database access, or
persistence mutation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, cast

import typer
from rich.console import Console

from constructionsight.ceqanet_operator_report import build_ceqanet_operator_report
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="Build CEQAnet operator Markdown reports.")
console = Console(width=240, color_system=None)


@app.callback()
def main() -> None:
    """Build CEQAnet operator Markdown reports."""


def _load_json_object(input_path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""

    try:
        payload = json.loads(read_runtime_text(input_path))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{input_path} is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter(f"{input_path} must contain a JSON object.")
    return cast(dict[str, Any], payload)


def _build_report_payload(operator_package: dict[str, Any]) -> dict[str, object]:
    """Build report payload and convert validation errors to CLI errors."""

    try:
        return build_ceqanet_operator_report(operator_package).to_dict()
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _write_markdown_file(output_path: Path, markdown: str) -> None:
    """Write deterministic UTF-8 Markdown output."""
    write_runtime_text(output_path, markdown)


def _write_json_file(output_path: Path, payload: dict[str, object]) -> None:
    """Write deterministic UTF-8 JSON output."""
    write_runtime_text(
        output_path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


@app.command("build")
def build_operator_report(
    operator_package_path: Annotated[
        Path,
        typer.Option(
            "--operator-package",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Existing CEQAnet operator package JSON.",
        ),
    ],
    output_path: Annotated[
        Path | None,
        typer.Option("--output", help="Write Markdown report to a file."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit report payload as machine-readable JSON."),
    ] = False,
    json_output_path: Annotated[
        Path | None,
        typer.Option("--json-output-path", help="Write JSON report payload to a file."),
    ] = None,
) -> None:
    """Build a non-mutating CEQAnet operator Markdown report."""

    operator_package = _load_json_object(operator_package_path)
    payload = _build_report_payload(operator_package)
    metadata = cast(dict[str, object], payload["metadata"])
    metadata["input"] = {"operator_package_path": str(operator_package_path)}
    markdown = cast(str, payload["markdown"])

    if json_output_path is not None:
        _write_json_file(json_output_path, payload)
        typer.echo(f"Wrote CEQAnet operator report JSON to {json_output_path}.")
        return
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    if output_path is not None:
        _write_markdown_file(output_path, markdown)
        typer.echo(f"Wrote CEQAnet operator Markdown report to {output_path}.")
        return
    console.print(markdown)
