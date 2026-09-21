"""Source registry update plan and controlled apply CLI."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
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
from constructionsight.source_registry_apply_models import SourceRegistryApplyReport
from constructionsight.source_registry_apply_service import SourceRegistryApplyError
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
)
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.source_registry_update_plan_service import (
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.storage.runtime_artifacts import (
    RuntimeArtifactError,
    anchored_artifact_parent,
    read_runtime_artifact,
    read_runtime_text,
    write_runtime_text,
)

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



_TRANSACTION_JOURNAL_LIMIT = 32 * 1024 * 1024


def _digest_bytes(content: bytes | None) -> str | None:
    return hashlib.sha256(content).hexdigest() if content is not None else None


def _optional_artifact(path: Path, *, limit: int = 16 * 1024 * 1024) -> bytes | None:
    try:
        return read_runtime_artifact(path, max_bytes=limit)
    except FileNotFoundError:
        return None


@contextmanager
def _serialized_registry_target(target: Path) -> Iterator[tuple[int, str]]:
    """Serialize cooperating registry writers using an inode-stable, permanent lock."""
    if os.name != "posix":
        raise RuntimeArtifactError("native registry transaction locking is unavailable")
    import fcntl

    with anchored_artifact_parent(target, create_parents=True) as (parent, name):
        identity = hashlib.sha256(name.encode("utf-8")).hexdigest()
        lock_name = f".source-registry-{identity}.lock"
        journal_name = f".source-registry-{identity}.pending.json"
        fd = os.open(
            lock_name,
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
            0o600, dir_fd=parent,
        )
        try:
            opened = os.fstat(fd)
            if (
                not stat.S_ISREG(opened.st_mode)
                or opened.st_uid != os.geteuid()
                or opened.st_nlink != 1
                or stat.S_IMODE(opened.st_mode) != 0o600
            ):
                raise RuntimeArtifactError("registry transaction lock must be private and owned")
            fcntl.flock(fd, fcntl.LOCK_EX)
            current = os.stat(lock_name, dir_fd=parent, follow_symlinks=False)
            if (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino):
                raise RuntimeArtifactError("registry transaction lock entry was replaced")
            os.fsync(parent)
            yield parent, journal_name
        finally:
            os.close(fd)


def _pending_identity(
    *, source: Path, plan: Path, target: Path, audit: Path, backup: Path | None,
    approved: str, operator: str, reason: str, overwrite: bool, in_place: bool,
) -> dict[str, object]:
    return {
        "source": str(source.absolute()),
        "plan": str(plan.absolute()),
        "target": str(target.absolute()),
        "audit": str(audit.absolute()),
        "backup": str(backup.absolute()) if backup is not None else None,
        "approved": approved, "operator": operator, "reason": reason,
        "overwrite": overwrite, "in_place": in_place,
    }


def _pending_text(record: dict[str, object]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


def _complete_pending_registry_apply(
    record: dict[str, object],
    *, target: Path, audit: Path, journal: Path, parent: int, journal_name: str,
) -> SourceRegistryApplyReport:
    """Complete only the audit of an already durably committed exact target."""
    target_bytes = _optional_artifact(target)
    target_sha = record["updated_target_sha"]
    if _digest_bytes(target_bytes) != target_sha:
        raise RuntimeArtifactError(
            "pending registry target is not the exact committed result; "
            "manual reconciliation required before any reapply"
        )
    report_text = record["audit_text"]
    if not isinstance(report_text, str):
        raise RuntimeArtifactError("pending registry audit content is invalid")
    report = SourceRegistryApplyReport.model_validate_json(report_text)
    if report.updated_registry_digest != (
        source_registry_digest(_sources_from_json(target_bytes.decode("utf-8")))
    ):
        raise RuntimeArtifactError("pending audit does not describe the committed registry")
    if report.plan_digest != record["approved"]:
        raise RuntimeArtifactError("pending registry audit plan identity disagrees")
    audit_sha = _digest_bytes(report_text.encode("utf-8"))
    observed_audit = _digest_bytes(_optional_artifact(audit))
    if observed_audit != audit_sha:
        if observed_audit != record["audit_before"]:
            raise RuntimeArtifactError("audit output changed outside the pending transaction")
        _atomic_write_text(audit, report_text, overwrite=record["overwrite"] is True)
        if _digest_bytes(_optional_artifact(audit)) != audit_sha:
            raise RuntimeArtifactError("registry audit publication could not be verified")
    if _digest_bytes(_optional_artifact(target)) != target_sha:
        raise RuntimeArtifactError("registry target changed during audit publication")
    current_journal = _optional_artifact(journal, limit=_TRANSACTION_JOURNAL_LIMIT)
    if current_journal != _pending_text(record).encode("utf-8"):
        raise RuntimeArtifactError("pending registry transaction journal changed")
    os.unlink(journal_name, dir_fd=parent)
    os.fsync(parent)
    return report


def _recover_pending_registry_apply(
    *, source: Path, plan_path: Path, target: Path, audit: Path, backup: Path | None,
    approved: str, operator: str, reason: str, overwrite: bool, in_place: bool,
    journal: Path, parent: int, journal_name: str,
) -> SourceRegistryApplyReport | None:
    raw = _optional_artifact(journal, limit=_TRANSACTION_JOURNAL_LIMIT)
    if raw is None:
        return None
    candidate: Any = json.loads(raw.decode("utf-8"))
    expected = _pending_identity(
        source=source, plan=plan_path, target=target, audit=audit, backup=backup,
        approved=approved, operator=operator, reason=reason,
        overwrite=overwrite, in_place=in_place,
    )
    if (
        not isinstance(candidate, dict)
        or set(candidate) != {*expected, "version", "updated_target_sha",
                              "audit_before", "audit_text"}
        or candidate.get("version") != 1
        or any(type(candidate[key]) is not type(value) or candidate[key] != value
               for key, value in expected.items())
    ):
        raise RuntimeArtifactError(
            "pending registry transaction is not this exact apply; "
            "manual reconciliation required before any reapply"
        )
    if (
        not isinstance(candidate["updated_target_sha"], str)
        or len(candidate["updated_target_sha"]) != 64
        or candidate["audit_before"] is not None and (
            not isinstance(candidate["audit_before"], str)
            or len(candidate["audit_before"]) != 64
        )
    ):
        raise RuntimeArtifactError("pending registry transaction contains invalid digests")
    current_plan = _load_plan(plan_path)
    if current_plan.plan_digest != approved:
        raise RuntimeArtifactError("pending registry transaction plan changed")
    return _complete_pending_registry_apply(
        candidate, target=target, audit=audit,
        journal=journal, parent=parent, journal_name=journal_name,
    )


def _finalize_registry_apply(
    *, record: dict[str, object], target: Path, audit: Path,
    journal: Path, parent: int, journal_name: str,
) -> SourceRegistryApplyReport:
    try:
        return _complete_pending_registry_apply(
            record, target=target, audit=audit,
            journal=journal, parent=parent, journal_name=journal_name,
        )
    except (OSError, RuntimeArtifactError) as exc:
        if _digest_bytes(_optional_artifact(target)) == record["updated_target_sha"]:
            _abort(
                "Registry target committed, but success audit publication failed; "
                "do not reapply until the target and audit are reconciled by an "
                f"exact retry: {exc}"
            )
        _abort(f"Registry apply incomplete; pending transaction requires reconciliation: {exc}")


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
    resolved_operator = _require_authorization_value(operator_id, "--operator-id")
    resolved_reason = _require_authorization_value(
        authorization_reason, "--authorization-reason",
    )
    with _serialized_registry_target(target_path) as (pinned_parent, journal_name):
        journal = target_path.with_name(journal_name)
        lock_path = target_path.with_name(journal_name.replace(".pending.json", ".lock"))
        reserved = {journal.absolute(), lock_path.absolute()}
        if any(path.absolute() in reserved for path in apply_paths.values()):
            _abort("registry transaction metadata must not overlap an input or output")
        recovered = _recover_pending_registry_apply(
            source=registry_path, plan_path=plan_path, target=target_path,
            audit=audit_output, backup=backup_output,
            approved=approved_plan_digest.strip(), operator=resolved_operator,
            reason=resolved_reason, overwrite=overwrite, in_place=in_place,
            journal=journal, parent=pinned_parent, journal_name=journal_name,
        )
        if recovered is not None:
            report = recovered
            console.print("Recovered exact pending source registry transaction.")
        else:
            if not in_place:
                _require_available_output(target_path, overwrite=overwrite)
            _require_available_output(audit_output, overwrite=overwrite)
            if backup_output is not None:
                _require_available_output(backup_output, overwrite=overwrite)

            original_registry_text = read_runtime_text(registry_path)
            sources = _sources_from_json(original_registry_text)
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

            updated_json = _registry_json(list(authorized.sources))
            report = authorized.report
            audit_json = f"{json.dumps(report.to_dict(), indent=2)}\n"
            updated_sha = _digest_bytes(updated_json.encode("utf-8"))
            if in_place and _digest_bytes(_optional_artifact(target_path)) != (
                _digest_bytes(original_registry_text.encode("utf-8"))
            ):
                _abort("registry changed while preparing in-place publication")
            record: dict[str, object] = {
                **_pending_identity(
                    source=registry_path, plan=plan_path, target=target_path,
                    audit=audit_output, backup=backup_output,
                    approved=approved_plan_digest.strip(), operator=resolved_operator,
                    reason=resolved_reason, overwrite=overwrite, in_place=in_place,
                ),
                "version": 1,
                "updated_target_sha": updated_sha,
                "audit_before": _digest_bytes(_optional_artifact(audit_output)),
                "audit_text": audit_json,
            }
            write_runtime_text(
                journal, _pending_text(record),
                overwrite=False, max_bytes=_TRANSACTION_JOURNAL_LIMIT,
            )
            if backup_output is not None:
                _atomic_write_text(
                    backup_output, original_registry_text, overwrite=overwrite,
                )
            _atomic_write_text(
                target_path, updated_json, overwrite=in_place or overwrite,
            )
            report = _finalize_registry_apply(
                record=record, target=target_path, audit=audit_output,
                journal=journal, parent=pinned_parent, journal_name=journal_name,
            )

    console.print(f"Applied {report.applied_count} source registry status update(s).")
    console.print(f"Updated registry: {target_path}")
    console.print(f"Audit report: {audit_output}")
    console.print(f"Registry digest: {report.updated_registry_digest}")
    console.print(f"Plan digest: {report.plan_digest}")
