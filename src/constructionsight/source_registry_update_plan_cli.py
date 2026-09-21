"""Source registry update plan and controlled apply CLI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.models import PublicSource
from constructionsight.operator_services.source_registry_service import (
    apply_authorized_source_registry_update_plan,
    build_authorized_source_registry_update_plan,
)
from constructionsight.source_registry_apply_service import SourceRegistryApplyError
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
)
from constructionsight.source_registry_update_plan_service import (
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text

app = typer.Typer(help="ConstructionSight source registry update plan and apply tools.")
console = Console()


def _abort(message: str) -> NoReturn:
    """Emit a deterministic operator error without Rich wrapping or styling."""

    typer.echo(message, err=True)
    raise typer.Exit(code=2)


def _load_sources_from_json(path: Path) -> list[PublicSource]:
    data: Any = json.loads(read_runtime_text(path))
    if not isinstance(data, list):
        _abort("Registry JSON must be a list.")
    return [PublicSource.model_validate(item) for item in data]


def _load_observations(path: Path | None) -> list[SourceVerificationObservation]:
    if path is None:
        return []
    data: Any = json.loads(read_runtime_text(path))
    if not isinstance(data, list):
        _abort("Observation JSON must be a list.")
    return [SourceVerificationObservation.model_validate(item) for item in data]


def _load_plan(path: Path) -> SourceRegistryUpdatePlanReport:
    data: Any = json.loads(read_runtime_text(path))
    return SourceRegistryUpdatePlanReport.model_validate(data)


def _registry_json(sources: list[PublicSource]) -> str:
    payload = [source.model_dump(mode="json") for source in sources]
    return f"{json.dumps(payload, indent=2)}\n"


def _atomic_write_text(path: Path, content: str, *, overwrite: bool = True) -> None:
    write_runtime_text(path, content, overwrite=overwrite)


def _require_available_output(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        _abort(f"Output path already exists; use --overwrite: {path}")


def _require_distinct_paths(paths: dict[str, Path]) -> None:
    resolved: dict[Path, str] = {}
    for label, path in paths.items():
        canonical = path.resolve()
        previous = resolved.get(canonical)
        if previous is not None:
            _abort(f"{label} path must differ from {previous} path: {path}")
        resolved[canonical] = label


def _require_authorization_value(value: str | None, option: str) -> str:
    if value is None or not value.strip():
        _abort(f"{option} is required for this high-impact operation.")
    return value.strip()


@app.callback()
def source_registry_update_root() -> None:
    """ConstructionSight source registry update plan and apply commands."""


@app.command("plan")
def source_registry_update_plan(
    registry_path: Annotated[Path, typer.Argument(help="Path to source registry JSON.")],
    observations_path: Annotated[
        Path | None,
        typer.Option("--observations-path", help="Optional operator observation JSON list."),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Optional output path for plan JSON."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json-output")] = False,
    check_http: Annotated[bool, typer.Option("--check-http")] = False,
    operator_id: Annotated[
        str | None,
        typer.Option(
            "--operator-id",
            help="Explicit local operator audit identity required with --check-http.",
        ),
    ] = None,
    authorization_reason: Annotated[
        str | None,
        typer.Option(
            "--authorization-reason",
            help="Nonblank reason required with --check-http.",
        ),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Allow replacement of an existing plan output file."),
    ] = False,
) -> None:
    """Build a dry-run source registry update plan without writing registry data."""

    sources = _load_sources_from_json(registry_path)
    observations = _load_observations(observations_path)
    if check_http:
        resolved_operator = _require_authorization_value(operator_id, "--operator-id")
        resolved_reason = _require_authorization_value(
            authorization_reason,
            "--authorization-reason",
        )
        try:
            report = build_authorized_source_registry_update_plan(
                sources,
                default_adapter_family_specs(),
                observations=observations,
                caller_confirmation=True,
                authorization_reason=resolved_reason,
                operator_id=resolved_operator,
            )
        except (AuthorizationDeniedError, ValueError) as exc:
            _abort(str(exc))
    else:
        report = build_source_registry_update_plan(
            sources,
            default_adapter_family_specs(),
            check_http=False,
            observations=observations,
        )

    rendered = json.dumps(report.to_dict(), indent=2)
    if output is not None:
        plan_paths = {
            "registry input": registry_path,
            "plan output": output,
        }
        if observations_path is not None:
            plan_paths["observations input"] = observations_path
        _require_distinct_paths(plan_paths)
        _require_available_output(output, overwrite=overwrite)
        _atomic_write_text(output, f"{rendered}\n", overwrite=overwrite)
        console.print(f"Wrote source registry update plan to {output}")
        console.print(f"Registry digest: {report.registry_digest}")
        console.print(f"Plan digest: {report.plan_digest}")
        return
    if json_output:
        console.print_json(rendered)
        return

    summary = Table(title="ConstructionSight Source Registry Update Plan")
    summary.add_column("Metric")
    summary.add_column("Value")
    summary.add_row("Source records", str(report.source_count))
    summary.add_row("Updates proposed", str(report.update_count))
    summary.add_row("Registry digest", report.registry_digest)
    summary.add_row("Plan digest", report.plan_digest)
    for action, count in sorted(report.action_counts.items()):
        summary.add_row(action, str(count))
    console.print(summary)

    rows = Table(title="Source Registry Update Plan Rows")
    rows.add_column("Source")
    rows.add_column("Current")
    rows.add_column("Proposed")
    rows.add_column("Update")
    rows.add_column("Next action")
    for row in report.rows:
        rows.add_row(
            row.source_name,
            row.current_verification_status,
            row.proposed_verification_status or "none",
            str(row.update_required),
            row.next_action,
        )
    console.print(rows)


@app.command("apply")
def source_registry_apply(
    registry_path: Annotated[Path, typer.Argument(help="Current source registry JSON.")],
    plan_path: Annotated[Path, typer.Argument(help="Approved source update plan JSON.")],
    approved_plan_digest: Annotated[
        str,
        typer.Option(
            "--approved-plan-digest",
            help="Exact SHA-256 digest printed by the reviewed plan command.",
        ),
    ],
    audit_output: Annotated[
        Path,
        typer.Option("--audit-output", help="Required output path for the apply audit report."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", help="Write the updated registry to a separate file."),
    ] = None,
    in_place: Annotated[
        bool,
        typer.Option("--in-place", help="Replace the current registry after writing a backup."),
    ] = False,
    backup_output: Annotated[
        Path | None,
        typer.Option("--backup-output", help="Required backup path when using --in-place."),
    ] = None,
    apply_changes: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Additional caller confirmation; not the operative authorization.",
        ),
    ] = False,
    operator_id: Annotated[
        str | None,
        typer.Option("--operator-id", help="Explicit local operator audit identity."),
    ] = None,
    authorization_reason: Annotated[
        str | None,
        typer.Option("--authorization-reason", help="Nonblank reason for this exact apply."),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Allow replacement of output, audit, or backup files."),
    ] = False,
) -> None:
    """Apply an approved evidence-backed plan with atomic file replacement."""

    if not apply_changes:
        _abort("Explicit --apply caller confirmation is required.")
    if in_place and output is not None:
        _abort("Use either --in-place or --output, not both.")
    if not in_place and output is None:
        _abort("Use --output or explicitly select --in-place.")
    if in_place and backup_output is None:
        _abort("--backup-output is required with --in-place.")
    if not in_place and backup_output is not None:
        _abort("--backup-output is valid only with --in-place.")

    target_path = registry_path if in_place else output
    if target_path is None:
        _abort("Updated registry target could not be resolved.")

    apply_paths = {
        "registry input": registry_path,
        "plan input": plan_path,
        "audit output": audit_output,
    }
    if in_place:
        if backup_output is None:
            _abort("--backup-output is required with --in-place.")
        apply_paths["backup output"] = backup_output
    else:
        apply_paths["updated registry output"] = target_path
    _require_distinct_paths(apply_paths)

    if not in_place:
        _require_available_output(target_path, overwrite=overwrite)
    _require_available_output(audit_output, overwrite=overwrite)
    if backup_output is not None:
        _require_available_output(backup_output, overwrite=overwrite)

    resolved_operator = _require_authorization_value(operator_id, "--operator-id")
    resolved_reason = _require_authorization_value(
        authorization_reason,
        "--authorization-reason",
    )
    sources = _load_sources_from_json(registry_path)
    plan = _load_plan(plan_path)
    try:
        authorized = apply_authorized_source_registry_update_plan(
            sources,
            plan,
            expected_plan_digest=approved_plan_digest.strip(),
            expected_registry_digest=plan.registry_digest,
            target_path_identity=str(target_path.resolve()),
            caller_confirmation=apply_changes,
            authorization_reason=resolved_reason,
            operator_id=resolved_operator,
        )
    except (AuthorizationDeniedError, SourceRegistryApplyError, ValueError) as exc:
        _abort(str(exc))

    updated_sources = list(authorized.sources)
    report = authorized.report
    if backup_output is not None:
        _atomic_write_text(backup_output, read_runtime_text(registry_path), overwrite=overwrite)
    _atomic_write_text(
        audit_output,
        f"{json.dumps(report.to_dict(), indent=2)}\n",
        overwrite=overwrite,
    )
    _atomic_write_text(
        target_path, _registry_json(updated_sources), overwrite=in_place or overwrite,
    )
    console.print(f"Applied {report.applied_count} source registry status update(s).")
    console.print(f"Updated registry: {target_path}")
    console.print(f"Audit report: {audit_output}")
    console.print(f"Registry digest: {report.updated_registry_digest}")
    console.print(f"Plan digest: {report.plan_digest}")
