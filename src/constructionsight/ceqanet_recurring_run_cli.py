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
from typer.models import OptionInfo

from constructionsight.authorization_decision import AuthorizationDeniedError
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
)
from constructionsight.ceqanet_recurring_run_verifier import (
    verify_ceqanet_recurring_run_execution,
)
from constructionsight.models import PublicSource
from constructionsight.operator_services.ceqanet_recurring_run_service import (
    execute_authorized_ceqanet_recurring_run,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="Build and execute governed CEQAnet recurring-run manifests.")
console = Console(width=240, color_system=None)
_ModelT = TypeVar("_ModelT", bound=BaseModel)


@app.callback()
def main() -> None:
    """Build and execute governed CEQAnet recurring-run manifests."""


def _load_json(path: Path) -> Any:
    try:
        return json.loads(read_runtime_text(path))
    except (OSError, json.JSONDecodeError) as exc:
        raise typer.BadParameter(f"{path} is not valid readable JSON.") from exc


def _load_model(path: Path, model_type: type[_ModelT]) -> _ModelT:
    try:
        return model_type.model_validate(_load_json(path))
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
    write_runtime_text(path, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    typer.echo(f"Wrote {path}.")


def _registry_option() -> OptionInfo:
    return cast(
        OptionInfo,
        typer.Option(
            "--registry",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Current source registry JSON used for stale-state validation.",
        ),
    )


def _checklist_option() -> OptionInfo:
    return cast(
        OptionInfo,
        typer.Option(
            "--checklist",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Current source checklist JSON used for stale-evidence validation.",
        ),
    )


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
    registry_path: Annotated[Path, _registry_option()],
    checklist_path: Annotated[Path, _checklist_option()],
    source_key: Annotated[
        str,
        typer.Option("--source-key", help="Exact checklist source key."),
    ],
    output_path: Annotated[
        Path,
        typer.Option("--output", help="Definition JSON output path."),
    ],
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
    high_signal_only: Annotated[bool, typer.Option("--high-signal-only")] = False,
    window_field: Annotated[
        CeqanetWindowField,
        typer.Option(help="Date field bounded by each exact manifest window."),
    ] = CeqanetWindowField.RECEIVED,
    page_size: Annotated[
        int,
        typer.Option(min=1, max=100, help="Page size, capped at 100."),
    ] = 25,
    max_pages: Annotated[
        int,
        typer.Option(min=1, max=10, help="Page count, capped at 10."),
    ] = 1,
    execution_base_url: Annotated[
        str,
        typer.Option(help="Official CEQAnet execution host root."),
    ] = "https://ceqanet.lci.ca.gov/",
    requires_login: Annotated[bool, typer.Option()] = False,
    has_captcha: Annotated[bool, typer.Option()] = False,
    robots_disallows_collection: Annotated[bool, typer.Option()] = False,
    terms_disallow_collection: Annotated[bool, typer.Option()] = False,
    paywalled: Annotated[bool, typer.Option()] = False,
    timeout_seconds: Annotated[
        float,
        typer.Option(min=0.001, max=20.0),
    ] = 20.0,
    max_body_chars: Annotated[
        int,
        typer.Option(min=1, max=50_000),
    ] = 50_000,
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
    _write_json(
        output_path,
        cast(dict[str, object], definition.model_dump(mode="json")),
    )
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
    window_start: Annotated[
        str,
        typer.Option(help="Inclusive window start, YYYY-MM-DD."),
    ],
    window_end: Annotated[
        str,
        typer.Option(help="Inclusive window end, YYYY-MM-DD."),
    ],
    output_path: Annotated[
        Path,
        typer.Option("--output", help="Manifest JSON output path."),
    ],
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
    _write_json(
        output_path,
        cast(dict[str, object], manifest.model_dump(mode="json")),
    )
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
    registry_path: Annotated[Path, _registry_option()],
    checklist_path: Annotated[Path, _checklist_option()],
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help="Optional local audit identity; this is not authentication.",
        ),
    ] = None,
    authorization_reason: Annotated[
        str,
        typer.Option(
            "--authorization-reason",
            help="Reason for this exact foreground manifest attempt.",
        ),
    ] = "Execute one reviewed CEQAnet recurring-run attempt.",
    attempt_sequence: Annotated[
        int,
        typer.Option(min=1, help="Positive manual attempt sequence."),
    ] = 1,
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
    output_path: Annotated[
        Path,
        typer.Option("--output", help="Execution JSON output path."),
    ] = Path("ceqanet-run-execution.json"),
) -> None:
    """Authorize and execute one exact foreground recurring-run attempt."""

    definition = _load_model(definition_path, CeqanetRecurringRunDefinition)
    manifest = _load_model(manifest_path, CeqanetRecurringRunManifest)
    checklist = _load_model(checklist_path, SourceVerificationChecklistReport)
    try:
        result = execute_authorized_ceqanet_recurring_run(
            definition=definition,
            manifest=manifest,
            sources=_load_registry(registry_path),
            checklist_report=checklist,
            attempt_sequence=attempt_sequence,
            caller_confirmation=execute_live,
            authorization_reason=authorization_reason,
            operator_id=operator_id,
        )
    except (AuthorizationDeniedError, ValueError) as exc:
        typer.echo(f"CEQAnet recurring-run execution blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    _write_json(
        output_path,
        cast(dict[str, object], result.execution.model_dump(mode="json")),
    )
    typer.echo(
        f"Authorization decision: {result.authorization.decision.decision_id}"
    )
    typer.echo(
        f"Authorization preflight: {result.authorization.preflight.preflight_id}"
    )


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
    registry_path: Annotated[Path, _registry_option()],
    checklist_path: Annotated[Path, _checklist_option()],
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
) -> None:
    """Verify artifacts and their current source-evidence authorization."""

    verification = verify_ceqanet_recurring_run_execution(
        _load_model(definition_path, CeqanetRecurringRunDefinition),
        _load_model(manifest_path, CeqanetRecurringRunManifest),
        _load_model(execution_path, CeqanetRecurringRunExecution),
        _load_registry(registry_path),
        _load_model(checklist_path, SourceVerificationChecklistReport),
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
