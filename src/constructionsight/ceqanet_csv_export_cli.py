"""Operator CLI for governed official CEQAnet CSV exports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

from constructionsight.ceqanet_csv_export_models import (
    CeqanetCsvExportExecution,
    CeqanetCsvExportRequest,
    CeqanetCsvScope,
)
from constructionsight.ceqanet_csv_export_service import (
    build_ceqanet_csv_export_url,
    execute_ceqanet_csv_export,
    parse_ceqanet_csv_bytes,
    verify_ceqanet_csv_execution,
)

app = typer.Typer(help="Governed official CEQAnet CSV export tools.")
console = Console()


def _write_json(path: Path, payload: Any, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise typer.BadParameter(f"output already exists: {path}; pass --overwrite to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _request(
    *,
    sch_number: str,
    document_id: int | None,
) -> CeqanetCsvExportRequest:
    scope = CeqanetCsvScope.DOCUMENT if document_id is not None else CeqanetCsvScope.PROJECT
    return CeqanetCsvExportRequest(
        scope=scope,
        sch_number=sch_number,
        document_id=document_id,
    )


@app.command("plan")
def plan_csv_export(
    sch_number: Annotated[str, typer.Option("--sch", help="Ten-digit SCH number.")],
    document_id: Annotated[
        int | None,
        typer.Option("--document-id", min=1, help="Optional CEQAnet document ID."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional request JSON output path."),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Build a deterministic official CSV request without network access."""

    request = _request(sch_number=sch_number, document_id=document_id)
    payload = {
        "request": request.model_dump(mode="json"),
        "request_url": build_ceqanet_csv_export_url(request),
        "network_executed": False,
        "documents_downloaded": False,
        "persistence_mutated": False,
    }
    if output is not None:
        _write_json(output, payload, overwrite=overwrite)
        console.print(f"Wrote CEQAnet CSV request plan to {output}")
        return
    console.print_json(json.dumps(payload))


@app.command("execute")
def execute_csv_export(
    sch_number: Annotated[str, typer.Option("--sch", help="Ten-digit SCH number.")],
    output: Annotated[Path, typer.Option("--output", help="Execution JSON output path.")],
    document_id: Annotated[
        int | None,
        typer.Option("--document-id", min=1, help="Optional CEQAnet document ID."),
    ] = None,
    execute_live: Annotated[
        bool,
        typer.Option("--execute-live", help="Explicitly authorize one bounded public GET."),
    ] = False,
    timeout_seconds: Annotated[
        float,
        typer.Option("--timeout-seconds", min=0.1, max=120.0),
    ] = 20.0,
    max_body_bytes: Annotated[
        int,
        typer.Option("--max-body-bytes", min=1, max=10_000_000),
    ] = 2_000_000,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Execute one explicit bounded CSV export and retain exact response evidence."""

    if not execute_live:
        raise typer.BadParameter("explicit --execute-live authorization is required")
    request = _request(sch_number=sch_number, document_id=document_id)
    execution = execute_ceqanet_csv_export(
        request,
        execute_live=True,
        timeout_seconds=timeout_seconds,
        max_body_bytes=max_body_bytes,
    )
    _write_json(output, execution.model_dump(mode="json"), overwrite=overwrite)
    verification = verify_ceqanet_csv_execution(execution)
    console.print(f"Wrote CEQAnet CSV execution evidence to {output}")
    console.print(f"Verification passed: {verification.passed}")
    if not verification.passed:
        raise typer.Exit(code=1)


@app.command("verify")
def verify_csv_export(
    execution_path: Annotated[Path, typer.Argument(help="Execution JSON artifact path.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional verification JSON output path."),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Verify a retained CSV execution artifact without network access."""

    payload: Any = json.loads(execution_path.read_text(encoding="utf-8"))
    execution = CeqanetCsvExportExecution.model_validate(payload)
    verification = verify_ceqanet_csv_execution(execution)
    rendered = verification.model_dump(mode="json")
    if output is not None:
        _write_json(output, rendered, overwrite=overwrite)
        console.print(f"Wrote CEQAnet CSV verification to {output}")
    else:
        console.print_json(json.dumps(rendered))
    if not verification.passed:
        raise typer.Exit(code=1)


@app.command("parse")
def parse_csv_export(
    csv_path: Annotated[Path, typer.Argument(help="Retained CEQAnet CSV file.")],
    source_url: Annotated[str, typer.Option("--source-url", help="Official source URL.")],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional parse-report JSON output path."),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
) -> None:
    """Strictly parse a retained CSV file without network or persistence."""

    report = parse_ceqanet_csv_bytes(csv_path.read_bytes(), source_url=source_url)
    rendered = report.model_dump(mode="json")
    if output is not None:
        _write_json(output, rendered, overwrite=overwrite)
        console.print(f"Wrote CEQAnet CSV parse report to {output}")
        return
    console.print_json(json.dumps(rendered))
