"""Source registry update plan and controlled apply CLI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_registry_apply_service import (
    SourceRegistryApplyError,
    apply_source_registry_update_plan,
)
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
)
from constructionsight.source_registry_update_plan_service import (
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)

app = typer.Typer(help="ConstructionSight source registry update plan and apply tools.")
console = Console()


def _load_sources_from_json(path: Path) -> list[PublicSource]:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Registry JSON must be a list.")
    return [PublicSource.model_validate(item) for item in data]


def _load_observations(path: Path | None) -> list[SourceVerificationObservation]:
    if path is None:
        return []
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise typer.BadParameter("Observation JSON must be a list.")
    return [SourceVerificationObservation.model_validate(item) for item in data]


def _load_plan(path: Path) -> SourceRegistryUpdatePlanReport:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    return SourceRegistryUpdatePlanReport.model_validate(data)


def _registry_json(sources: list[PublicSource]) -> str:
    payload = [source.model_dump(mode="json") for source in sources]
    return f"{json.dumps(payload, indent=2)}\n"


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _require_available_output(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise typer.BadParameter(f"Output path already exists; use --overwrite: {path}")


def _require_distinct_paths(paths: dict[str, Path]) -> None:
    resolved: dict[Path, str] = {}
    for label, path in paths.items():
        canonical = path.resolve()
        previous = resolved.get(canonical)
        if previous is not None:
            raise typer.BadParameter(
                f"{label} path must differ from {previous} path: {path}"
            )
        resolved[canonical] = label


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
) -> None:
    """Build a dry-run source registry update plan without writing registry data."""

    report = build_source_registry_update_plan(
        _load_sources_from_json(registry_path),
        default_adapter_family_specs(),
        check_http=check_http,
        observations=_load_observations(observations_path),
    )
    rendered = json.dumps(report.to_dict(), indent=2)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"{rendered}\n", encoding="utf-8")
        console.print(f"Wrote source registry update plan to {output}")
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
        typer.Option("--apply", help="Explicitly authorize registry status changes."),
    ] = False,
    overwrite: Annotated[
        bool,
        typer.Option("--overwrite", help="Allow replacement of output, audit, or backup files."),
    ] = False,
) -> None:
    """Apply an approved evidence-backed plan with atomic file replacement."""

    if not apply_changes:
        raise typer.BadParameter("Explicit --apply authorization is required.")
    if in_place and output is not None:
        raise typer.BadParameter("Use either --in-place or --output, not both.")
    if not in_place and output is None:
        raise typer.BadParameter("Use --output or explicitly select --in-place.")
    if in_place and backup_output is None:
        raise typer.BadParameter("--backup-output is required with --in-place.")
    if not in_place and backup_output is not None:
        raise typer.BadParameter("--backup-output is valid only with --in-place.")

    target_path = registry_path if in_place else output
    if target_path is None:
        raise typer.BadParameter("Updated registry target could not be resolved.")
    paths = {"registry target": target_path, "audit output": audit_output}
    if backup_output is not None:
        paths["backup output"] = backup_output
    _require_distinct_paths(paths)

    if not in_place:
        _require_available_output(target_path, overwrite=overwrite)
    _require_available_output(audit_output, overwrite=overwrite)
    if backup_output is not None:
        _require_available_output(backup_output, overwrite=overwrite)

    sources = _load_sources_from_json(registry_path)
    plan = _load_plan(plan_path)
    try:
        updated_sources, report = apply_source_registry_update_plan(
            sources,
            plan,
            approved_plan_digest=approved_plan_digest.strip(),
        )
    except SourceRegistryApplyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if backup_output is not None:
        _atomic_write_text(backup_output, registry_path.read_text(encoding="utf-8"))
    _atomic_write_text(target_path, _registry_json(updated_sources))
    _atomic_write_text(
        audit_output,
        f"{json.dumps(report.to_dict(), indent=2)}\n",
    )
    console.print(f"Applied {report.applied_count} source registry status update(s).")
    console.print(f"Updated registry: {target_path}")
    console.print(f"Audit report: {audit_output}")
    console.print(f"Plan digest: {report.plan_digest}")
