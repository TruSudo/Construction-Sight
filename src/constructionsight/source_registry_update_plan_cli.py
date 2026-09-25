"""Source registry update plan and controlled apply CLI."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
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
from constructionsight.source_registry_apply_service import (
    SourceRegistryApplyError,
    validate_source_registry_apply_snapshot,
)
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
)
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
    validate_runtime_artifact_bindings,
    write_runtime_text,
)

app = typer.Typer(help="ConstructionSight source registry update plan and apply tools.")
console = Console()


def _abort(message: str) -> NoReturn:
    """Emit a deterministic operator error without Rich wrapping or styling."""

    typer.echo(message, err=True)
    raise typer.Exit(code=2)


def _sources_from_json(text: str) -> list[PublicSource]:
    """Parse one already captured registry snapshot without reopening its path."""

    data: Any = json.loads(text)
    if not isinstance(data, list):
        _abort("Registry JSON must be a list.")
    return [PublicSource.model_validate(item) for item in data]


def _load_sources_from_json(path: Path) -> list[PublicSource]:
    return _sources_from_json(read_runtime_text(path))


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


def _atomic_write_text(
    path: Path, content: str, *, overwrite: bool = True,
    parent: int | None = None, max_bytes: int = 16 * 1024 * 1024,
) -> None:
    write_runtime_text(path, content, overwrite=overwrite, parent=parent, max_bytes=max_bytes)


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


@dataclass
class _RegistryArtifacts:
    """Pinned participants and stable locks held for the entire publication."""

    parents: dict[Path, int]
    bindings: list[tuple[int, str, int]]
    locks: list[tuple[int, str, int]]

    def parent(self, path: Path) -> int:
        return self.parents[path.absolute()]

    def check_locks(self) -> None:
        validate_runtime_artifact_bindings(self.bindings)
        for parent, name, descriptor in self.locks:
            opened = os.fstat(descriptor)
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (
                (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
                or not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
                or current.st_uid != os.geteuid()
                or stat.S_IMODE(current.st_mode) != 0o600
            ):
                raise RuntimeArtifactError(
                    "registry transaction lock entry was replaced or altered"
                )
            directory = os.fstat(parent)
            if directory.st_uid != os.geteuid() or stat.S_IMODE(directory.st_mode) & 0o022:
                raise RuntimeArtifactError(
                    "registry transaction output directory is no longer private"
                )

    def read(
        self, path: Path, *, limit: int = 16 * 1024 * 1024, durable: bool = False,
    ) -> bytes | None:
        self.check_locks()
        try:
            return read_runtime_artifact(
                path, max_bytes=limit, parent=self.parent(path), durable=durable,
            )
        except FileNotFoundError:
            return None

    def text(self, path: Path) -> str:
        content = self.read(path)
        if content is None:
            raise RuntimeArtifactError(f"registry transaction input is absent: {path}")
        return content.decode("utf-8")

    def write(
        self, path: Path, content: str, *, overwrite: bool, max_bytes: int = 16 * 1024 * 1024,
    ) -> None:
        self.check_locks()
        _atomic_write_text(
            path, content, overwrite=overwrite, parent=self.parent(path), max_bytes=max_bytes,
        )


def _transaction_names(target: Path) -> tuple[str, str]:
    identity = hashlib.sha256(target.name.encode("utf-8")).hexdigest()
    return f".source-registry-{identity}.lock", f".source-registry-{identity}.pending.json"


@contextmanager
def _serialized_registry_target(
    target: Path, *, inputs: tuple[Path, ...], outputs: tuple[Path, ...],
) -> Iterator[_RegistryArtifacts]:
    """Pin all participants; lock every writable artifact in a deterministic order."""
    if os.name != "posix":
        raise RuntimeArtifactError("native registry transaction locking is unavailable")
    import fcntl

    journal = target.with_name(_transaction_names(target)[1])
    artifacts = _RegistryArtifacts(parents={}, bindings=[], locks=[])
    with ExitStack() as stack:
        for path in dict.fromkeys((*inputs, *outputs, journal)):
            parent, _ = stack.enter_context(anchored_artifact_parent(
                path, create_parents=path in (*outputs, journal),
                retained_bindings=artifacts.bindings,
            ))
            artifacts.parents[path.absolute()] = parent
        lock_entries: dict[tuple[int, int, str], tuple[int, str]] = {}
        reserved: set[tuple[int, int, str]] = set()
        for path in outputs:
            parent = artifacts.parent(path)
            info = os.fstat(parent)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o022:
                raise RuntimeArtifactError(
                    "registry transaction output directory must be owned and private"
                )
            lock_name, pending_name = _transaction_names(path)
            key = info.st_dev, info.st_ino, lock_name
            lock_entries[key] = parent, lock_name
            reserved.update((key, (info.st_dev, info.st_ino, pending_name)))
        for path in (*inputs, *outputs):
            info = os.fstat(artifacts.parent(path))
            if (info.st_dev, info.st_ino, path.name) in reserved:
                raise RuntimeArtifactError(
                    "registry transaction metadata must not overlap an input or output"
                )
        for key in sorted(lock_entries):
            parent, lock_name = lock_entries[key]
            fd = os.open(
                lock_name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK
                | getattr(os, "O_CLOEXEC", 0), 0o600, dir_fd=parent,
            )
            stack.callback(os.close, fd)
            artifacts.locks.append((parent, lock_name, fd))
            artifacts.check_locks()
            fcntl.flock(fd, fcntl.LOCK_EX)
            artifacts.check_locks()
            os.fsync(parent)
        yield artifacts
        artifacts.check_locks()


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
    *, target: Path, source: Path, audit: Path, backup: Path | None,
    journal: Path, artifacts: _RegistryArtifacts,
) -> SourceRegistryApplyReport:
    """Recover exact prepared bytes; publish success only after target verification."""
    if artifacts.read(journal, limit=_TRANSACTION_JOURNAL_LIMIT, durable=True) != (
        _pending_text(record).encode("utf-8")
    ):
        raise RuntimeArtifactError("pending registry transaction journal changed")
    target_text = record["target_text"]
    report_text = record["audit_text"]
    backup_text = record["backup_text"]
    if (
        not isinstance(target_text, str)
        or not isinstance(report_text, str)
        or (backup_text is not None and not isinstance(backup_text, str))
        or len(target_text.encode("utf-8")) > 16 * 1024 * 1024
        or len(report_text.encode("utf-8")) > 16 * 1024 * 1024
        or (
            backup_text is not None
            and len(backup_text.encode("utf-8")) > 16 * 1024 * 1024
        )
    ):
        raise RuntimeArtifactError("pending registry transaction output is invalid")
    target_sha = _digest_bytes(target_text.encode("utf-8"))
    if record["updated_target_sha"] != target_sha:
        raise RuntimeArtifactError("pending target bytes disagree with transaction identity")
    report = SourceRegistryApplyReport.model_validate_json(report_text)
    original_text = backup_text if record["in_place"] is True else artifacts.text(source)
    if not isinstance(original_text, str) or _digest_bytes(original_text.encode("utf-8")) != (
        record["source_before"]
    ):
        raise RuntimeArtifactError("pending registry original source is not intact")
    current_plan = SourceRegistryUpdatePlanReport.model_validate_json(
        artifacts.text(Path(str(record["plan"])))
    )
    validate_source_registry_apply_snapshot(
        _sources_from_json(original_text), current_plan, _sources_from_json(target_text), report,
        approved_plan_digest=str(record["approved"]),
    )
    if (
        report.updated_registry_digest != source_registry_digest(
            _sources_from_json(target_text)
        )
        or report.plan_digest != record["approved"]
    ):
        raise RuntimeArtifactError("pending audit does not describe the exact approved target")
    if record["in_place"] is not True and _digest_bytes(artifacts.read(source)) != (
        record["source_before"]
    ):
        raise RuntimeArtifactError("registry input changed during pending publication")
    target_before = record["target_before"]
    observed_target = _digest_bytes(artifacts.read(target))
    if observed_target not in (target_before, target_sha):
        raise RuntimeArtifactError(
            "pending registry target diverged; manual reconciliation required before any reapply"
        )
    audit_sha = _digest_bytes(report_text.encode("utf-8"))
    observed_audit = _digest_bytes(artifacts.read(audit))
    if observed_audit not in (record["audit_before"], audit_sha):
        raise RuntimeArtifactError(
            "pending registry audit diverged; manual reconciliation required"
        )
    if observed_target != target_sha and observed_audit == audit_sha:
        raise RuntimeArtifactError("success audit cannot precede authoritative registry commit")
    if backup is not None:
        if backup_text is None or _digest_bytes(backup_text.encode("utf-8")) != (
            record["source_before"]
        ):
            raise RuntimeArtifactError("pending registry backup is not the original source")
        backup_sha = _digest_bytes(backup_text.encode("utf-8"))
        existing_backup = _digest_bytes(artifacts.read(backup))
        if existing_backup not in (record["backup_before"], backup_sha):
            raise RuntimeArtifactError("pending registry backup diverged")
        if existing_backup != backup_sha:
            artifacts.write(
                backup, backup_text, overwrite=record["overwrite"] is True,
            )
        if _digest_bytes(artifacts.read(backup, durable=True)) != backup_sha:
            raise RuntimeArtifactError("registry backup publication could not be verified")
    elif backup_text is not None:
        raise RuntimeArtifactError("unrequested backup exists in transaction journal")
    if observed_target != target_sha:
        if _digest_bytes(artifacts.read(target)) != target_before:
            raise RuntimeArtifactError("registry target changed before commit")
        artifacts.write(
            target, target_text,
            overwrite=record["in_place"] is True or record["overwrite"] is True,
        )
    if _digest_bytes(artifacts.read(target, durable=True)) != target_sha:
        raise RuntimeArtifactError("registry target publication could not be verified")
    if _digest_bytes(artifacts.read(audit)) != audit_sha:
        if _digest_bytes(artifacts.read(audit)) != record["audit_before"]:
            raise RuntimeArtifactError("registry audit changed before success publication")
        artifacts.write(audit, report_text, overwrite=record["overwrite"] is True)
    if (
        _digest_bytes(artifacts.read(target, durable=True)) != target_sha
        or _digest_bytes(artifacts.read(audit, durable=True)) != audit_sha
        or (backup is not None and _digest_bytes(artifacts.read(backup, durable=True))
            != record["source_before"])
    ):
        raise RuntimeArtifactError("registry transaction could not verify its final artifacts")
    current_journal = artifacts.read(journal, limit=_TRANSACTION_JOURNAL_LIMIT)
    if current_journal != _pending_text(record).encode("utf-8"):
        raise RuntimeArtifactError("pending registry transaction journal changed")
    os.unlink(journal.name, dir_fd=artifacts.parent(journal))
    os.fsync(artifacts.parent(journal))
    return report


def _recover_pending_registry_apply(
    *, source: Path, plan_path: Path, target: Path, audit: Path, backup: Path | None,
    approved: str, operator: str, reason: str, overwrite: bool, in_place: bool,
    journal: Path, artifacts: _RegistryArtifacts,
) -> SourceRegistryApplyReport | None:
    raw = artifacts.read(journal, limit=_TRANSACTION_JOURNAL_LIMIT, durable=True)
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
        or set(candidate) != {
            *expected, "version", "updated_target_sha", "source_before",
            "target_before", "audit_before", "backup_before",
            "target_text", "audit_text", "backup_text",
        }
        or type(candidate.get("version")) is not int or candidate.get("version") != 1
        or any(type(candidate[key]) is not type(value) or candidate[key] != value
               for key, value in expected.items())
    ):
        raise RuntimeArtifactError(
            "pending registry transaction is not this exact apply; "
            "manual reconciliation required before any reapply"
        )
    for key in (
        "updated_target_sha", "source_before", "target_before",
        "audit_before", "backup_before",
    ):
        value = candidate[key]
        if value is not None and (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise RuntimeArtifactError("pending registry transaction contains invalid digests")
    if not all(isinstance(candidate[key], str) for key in ("updated_target_sha", "source_before")):
        raise RuntimeArtifactError("pending registry source or updated target digest is absent")
    current_plan = SourceRegistryUpdatePlanReport.model_validate_json(artifacts.text(plan_path))
    report_text = candidate["audit_text"]
    if not isinstance(report_text, str):
        raise RuntimeArtifactError("pending registry audit is invalid")
    report = SourceRegistryApplyReport.model_validate_json(report_text)
    if (
        current_plan.plan_digest != approved
        or current_plan.registry_digest != report.original_registry_digest
    ):
        raise RuntimeArtifactError("pending registry transaction plan changed")
    return _finalize_registry_apply(
        record=candidate, target=target, source=source, audit=audit, backup=backup,
        journal=journal, artifacts=artifacts,
    )


def _finalize_registry_apply(
    *, record: dict[str, object], target: Path, source: Path, audit: Path,
    backup: Path | None, journal: Path, artifacts: _RegistryArtifacts,
) -> SourceRegistryApplyReport:
    try:
        return _complete_pending_registry_apply(
            record, target=target, source=source, audit=audit, backup=backup,
            journal=journal, artifacts=artifacts,
        )
    except (OSError, ValueError) as exc:
        if _digest_bytes(artifacts.read(target)) == record["updated_target_sha"]:
            report_text = record["audit_text"]
            if isinstance(report_text, str) and _digest_bytes(artifacts.read(audit)) == (
                _digest_bytes(report_text.encode("utf-8"))
            ):
                _abort(
                    "Registry and audit contents match the prepared record, but "
                    "verification, cleanup or durability failed; inspect both "
                    "artifacts and the pending journal before any new apply: "
                    f"{exc}"
                )
            _abort(
                "Registry target contents are published, but transaction completion failed; "
                "do not reapply until the target and audit are reconciled by an "
                f"exact retry using the retained journal: {exc}"
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
    """Recoverably publish an approved plan; related files may be temporarily partial."""

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
    outputs = (target_path, audit_output) + ((backup_output,) if backup_output else ())
    with _serialized_registry_target(
        target_path, inputs=(registry_path, plan_path), outputs=outputs,
    ) as artifacts:
        journal = target_path.with_name(_transaction_names(target_path)[1])
        try:
            recovered = _recover_pending_registry_apply(
                source=registry_path, plan_path=plan_path, target=target_path,
                audit=audit_output, backup=backup_output,
                approved=approved_plan_digest.strip(), operator=resolved_operator,
                reason=resolved_reason, overwrite=overwrite, in_place=in_place,
                journal=journal, artifacts=artifacts,
            )
        except (OSError, ValueError) as exc:
            _abort(f"Pending registry transaction cannot be reconciled: {exc}")
        if recovered is not None:
            report = recovered
            console.print("Recovered exact pending source registry transaction.")
        else:
            if not in_place:
                _require_available_output(target_path, overwrite=overwrite)
            _require_available_output(audit_output, overwrite=overwrite)
            if backup_output is not None:
                _require_available_output(backup_output, overwrite=overwrite)

            original_registry_text = artifacts.text(registry_path)
            sources = _sources_from_json(original_registry_text)
            plan = SourceRegistryUpdatePlanReport.model_validate_json(artifacts.text(plan_path))
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
            source_sha = _digest_bytes(original_registry_text.encode("utf-8"))
            target_before = _digest_bytes(artifacts.read(target_path))
            if in_place and target_before != source_sha:
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
                "source_before": source_sha,
                "target_before": target_before,
                "audit_before": _digest_bytes(artifacts.read(audit_output)),
                "backup_before": (
                    _digest_bytes(artifacts.read(backup_output))
                    if backup_output is not None else None
                ),
                "target_text": updated_json,
                "audit_text": audit_json,
                "backup_text": original_registry_text if backup_output is not None else None,
            }
            try:
                artifacts.write(
                    journal, _pending_text(record),
                    overwrite=False, max_bytes=_TRANSACTION_JOURNAL_LIMIT,
                )
            except (OSError, ValueError) as exc:
                _abort(
                    "No registry publication attempted; pending journal preparation or "
                    f"durability failed. Inspect the pending record before exact retry: {exc}"
                )
            report = _finalize_registry_apply(
                record=record, target=target_path, source=registry_path,
                audit=audit_output, backup=backup_output,
                journal=journal, artifacts=artifacts,
            )

    console.print(f"Applied {report.applied_count} source registry status update(s).")
    console.print(f"Updated registry: {target_path}")
    console.print(f"Audit report: {audit_output}")
    console.print(f"Registry digest: {report.updated_registry_digest}")
    console.print(f"Plan digest: {report.plan_digest}")
