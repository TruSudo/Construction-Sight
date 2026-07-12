"""Operator CLI for governed CEQAnet recurring-run artifacts and execution."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Annotated, Any, TypeVar, cast

import typer
from pydantic import BaseModel, ValidationError
from rich.console import Console
from rich.table import Table

from constructionsight.ceqanet_recurring_run_models import (
    CeqanetAccessAssumptions,
    CeqanetRecurringQueryTemplate,
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetWindowField,
)
from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
    execute_ceqanet_recurring_run,
    verify_ceqanet_recurring_run_execution,
)
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)

app = typer.Typer(help="Build and execute governed CEQAnet recurring-run manifests.")
console = Console(width=240, color_system=None)
_ModelT = TypeVar("_ModelT", bound=BaseModel)


@app.callback()
def main() -> None:
    """Build and execute governed CEQAnet recurring-run manifests."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{path} is not valid JSON.") from exc


def _load_model(path: Path, model_type: type[_ModelT]) -> _ModelT:
    payload = _load_json(path)
    try:
        return model_type.model_validate(payload)
    except ValidationError as exc:
        raise typer.BadParameter(f"{path} does not match {model_type.__name__}.") from exc


def _load_registry(path: Path) -> list[PublicSource]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        raise typer.BadParameter(f"{path} must contain a JSON list.")
    try:
        return [PublicSource.model_validate(item) for item in payload]
    except ValidationError as exc:
        raise typer.BadParameter(f"{path} contains an invalid source record.") from exc


def _normalize_repeated(values: list[str] | None) -> list[str]:
    return [value for value in (values or []) if value.strip()]


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"{field_name} must use YYYY-MM-DD.") from exc


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    typer.echo(f"Wrote {path}.")


def _render_definition(definition: CeqanetRecurringRunDefinition) -> None:
    table = Table(title="CEQAnet Recurring-Run Definition")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "source_key",
        "source_name",
        "registry_public_url",
        "execution_base_url",
        "registry_verification_status",
        "checklist_status",
        "readiness",
        "definition_digest",
    ):
        table.add_row(field_name, str(getattr(definition, field_name)))
    table.add_row("blocker_count", str(len(definition.blockers)))
    table.add_row("evidence_ref_count", str(len(definition.evidence_refs)))
    console.print(table)


def _render_manifest(manifest: CeqanetRecurringRunManifest) -> None:
    table = Table(title="CEQAnet Recurring-Run Manifest")
    table.add_column("Field")
    table.add_column("Value")
    for field_name in (
        "run_id",
        "definition_digest",
        "source_key",
        "window_field",
        "window_start",
        "window_end",
        "readiness",
        "manifest_digest",
    ):
        table.add_row(field_name, str(getattr(manifest, field_name)))
    table.add_row("blocker_count", str(len(manifest.blockers)))
    console.print(table)


@app.command("build-definition")
def build_definition(
    registry_path: Annotated[
        Path,
        typer.Option(
            "--registry",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    checklist_path: Annotated[
        Path,
        typer.Option(
            "--checklist",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    source_key: Annotated[str, typer.Option("--source-key", help="Exact checklist source key.")],
    output_path: Annotated[Path, typer.Option("--output", help="Definition JSON output path.")],
    county: Annotated[
        list[str] | None,
        typer.Option("--county", help="Stable county filter. Repeat as needed."),
    ] = None,
    document_type: Annotated[
        list[str] | None,
        typer.Option("--document-type", help="Stable document-type filter."),
    ] = None,
    lead_agency: Annotated[
        list[str] | None,
        typer.Option("--lead-agency", help="Stable lead-agency filter."),
    ] = None,
    text: Annotated[
        list[str] | None,
        typer.Option("--text", help="Stable required text term."),
    ] = None,
    high_signal_only: Annotated[bool, typer.Option("--high-signal-only")] = False,
    window_field: Annotated[
        CeqanetWindowField,
        typer.Option(help="Date field bounded by each exact manifest window."),
    ] = CeqanetWindowField.RECEIVED,
    page_size: Annotated[int, typer.Option(help="Page size, capped at 100.")] = 25,
    max_pages: Annotated[int, typer.Option(help="Page count, capped at 10.")] = 1,
    execution_base_url: Annotated[
        str,
        typer.Option(help="Official CEQAnet execution host root."),
    ] = "https://ceqanet.lci.ca.gov/",
    requires_login: Annotated[bool, typer.Option()] = False,
    has_captcha: Annotated[bool, typer.Option()] = False,
    robots_disallows_collection: Annotated[bool, typer.Option()] = False,
    terms_disallow_collection: Annotated[bool, typer.Option()] = False,
    paywalled: Annotated[bool, typer.Option()] = False,
    timeout_seconds: Annotated[float, typer.Option()] = 20.0,
    max_body_chars: Annotated[int, typer.Option()] = 50_000,
) -> None:
    """Build a source- and evidence-bound recurring-run definition."""

    checklist = _load_model(checklist_path, SourceVerificationChecklistReport)
    try:
        definition = build_ceqanet_recurring_run_definition(
            _load_registry(registry_path),
            checklist,
            source_key=source_key,
            query_template=CeqanetRecurringQueryTemplate(
                counties=_normalize_repeated(county),
                document_types=_normalize_repeated(document_type),
                lead_agencies=_normalize_repeated(lead_agency),
                text_terms=_normalize_repeated(text),
                high_signal_only=high_signal_only,
                window_field=window_field,
                page_size=page_size,
                max_pages=max_pages,
            ),
            access_assumptions=CeqanetAccessAssumptions(
                requires_login=requires_login,
                has_captcha=has_captcha,
                robots_disallows_collection=robots_disallows_collection,
                terms_disallow_collection=terms_disallow_collection,
                paywalled=paywalled,
            ),
            execution_base_url=execution_base_url,
            timeout_seconds=timeout_seconds,
            max_body_chars=max_body_chars,
        )
    except (ValidationError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    _write_json(output_path, cast(dict[str, object], definition.model_dump(mode="json")))
    _render_definition(definition)


@app.command("build-manifest")
def build_manifest(
    definition_path: Annotated[
        Path,
        typer.Option(
            "--definition",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    window_start: Annotated[str, typer.Option(help="Inclusive window start, YYYY-MM-DD.")],
    window_end: Annotated[str, typer.Option(help="Inclusive window end, YYYY-MM-DD.")],
    output_path: Annotated[Path, typer.Option("--output", help="Manifest JSON output path.")],
) -> None:
    """Build one immutable exact-window manifest."""

    definition = _load_model(definition_path, CeqanetRecurringRunDefinition)
    try:
        manifest = build_ceqanet_recurring_run_manifest(
            definition,
            window_start=_parse_date(window_start, "window-start"),
            window_end=_parse_date(window_end, "window-end"),
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _write_json(output_path, cast(dict[str, object], manifest.model_dump(mode="json")))
    _render_manifest(manifest)


@app.command("execute")
def execute_manifest(
    definition_path: Annotated[
        Path,
        typer.Option(
            "--definition",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    manifest_path: Annotated[
        Path,
        typer.Option(
            "--manifest",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    attempt_sequence: Annotated[int, typer.Option(help="Positive retry/attempt sequence.")] = 1,
    execute_live: Annotated[
        bool,
        typer.Option("--execute-live", help="Required explicit authorization for network GETs."),
    ] = False,
    output_path: Annotated[Path, typer.Option("--output", help="Execution JSON output path.")] = Path(
        "ceqanet-run-execution.json"
    ),
) -> None:
    """Execute a ready manifest through the bounded CEQAnet listing executor."""

    definition = _load_model(definition_path, CeqanetRecurringRunDefinition)
    manifest = _load_model(manifest_path, CeqanetRecurringRunManifest)
    try:
        execution = execute_ceqanet_recurring_run(
            definition,
            manifest,
            attempt_sequence=attempt_sequence,
            execute_live=execute_live,
        )
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    _write_json(output_path, cast(dict[str, object], execution.model_dump(mode="json")))


@app.command("verify")
def verify_execution(
    definition_path: Annotated[
        Path,
        typer.Option(
            "--definition",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    manifest_path: Annotated[
        Path,
        typer.Option(
            "--manifest",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    execution_path: Annotated[
        Path,
        typer.Option(
            "--execution",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ],
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
) -> None:
    """Verify definition, manifest, and execution integrity."""

    verification = verify_ceqanet_recurring_run_execution(
        _load_model(definition_path, CeqanetRecurringRunDefinition),
        _load_model(manifest_path, CeqanetRecurringRunManifest),
        _load_model(execution_path, CeqanetRecurringRunExecution),
    )
    payload = verification.model_dump(mode="json")
    if json_output:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        table = Table(title="CEQAnet Recurring-Run Verification")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("Passed", str(verification.passed))
        table.add_row("Findings", str(verification.finding_count))
        table.add_row("Run ID", verification.run_id)
        console.print(table)
        for finding in verification.findings:
            typer.echo(f"- {finding}")
    if not verification.passed:
        raise typer.Exit(code=1)
