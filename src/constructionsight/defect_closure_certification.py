"""Incremental permanent defect-closure certification."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from constructionsight.governance_certification_core import GovernanceFinding, _finding

_ACTIVE_LEDGER_PATH: Final = "governance/active_defects.toml"
_RESOLVED_LEDGER_PATH: Final = "governance/resolved_defects.toml"
_ACTIVE_SCHEMA: Final = "constructionsight.active-defects/v1"
_RESOLVED_SCHEMA: Final = "constructionsight.resolved-defects/v2"
_ACTIVE_FIELDS: Final = frozenset(
    {
        "id",
        "severity",
        "area",
        "root_cause",
        "discovered_against",
        "required_resolution",
    }
)
_RESOLVED_FIELDS: Final = _ACTIVE_FIELDS | {
    "resolution_summary",
    "resolution_commit",
    "resolution_tree",
    "last_active_commit",
    "evidence_paths",
    "regression_tests",
    "closure_evidence",
}
_COMMIT_PATTERN: Final = re.compile(r"[0-9a-f]{40}")
_TREE_PATTERN: Final = re.compile(r"[0-9a-f]{40,64}")
_DEFECT_PATTERN: Final = re.compile(r"CS-SR-[0-9]{3}")


class DefectClosureError(ValueError):
    """Raised when Git history cannot prove a claimed defect closure."""


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise DefectClosureError(f"cannot execute git: {exc}") from exc


def _git_error(completed: subprocess.CompletedProcess[bytes]) -> str:
    return (
        completed.stderr.decode("utf-8", errors="replace").strip()
        or completed.stdout.decode("utf-8", errors="replace").strip()
        or "unknown git error"
    )


def _commit_exists(root: Path, commit: str) -> bool:
    return _run_git(root, "cat-file", "-e", f"{commit}^{{commit}}").returncode == 0


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    completed = _run_git(root, "merge-base", "--is-ancestor", ancestor, descendant)
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise DefectClosureError(f"cannot verify commit ancestry: {_git_error(completed)}")


def _tree_id(root: Path, commit: str) -> str:
    completed = _run_git(root, "rev-parse", f"{commit}^{{tree}}")
    if completed.returncode != 0:
        raise DefectClosureError(
            f"cannot resolve resolution tree: {_git_error(completed)}"
        )
    try:
        return completed.stdout.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise DefectClosureError("resolution tree identity is not ASCII") from exc


def _read_commit_toml(root: Path, commit: str, path: str) -> Mapping[str, Any]:
    completed = _run_git(root, "show", f"{commit}:{path}")
    if completed.returncode != 0:
        raise DefectClosureError(
            f"cannot read {path} from {commit}: {_git_error(completed)}"
        )
    try:
        return tomllib.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise DefectClosureError(f"{path} at {commit} is malformed: {exc}") from exc


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _active_facts(entry: object) -> dict[str, str]:
    if not isinstance(entry, dict) or set(entry) != _ACTIVE_FIELDS:
        raise DefectClosureError("active defect fields disagree with canonical schema")
    defect_id = entry.get("id")
    severity = entry.get("severity")
    discovered_against = entry.get("discovered_against")
    if not isinstance(defect_id, str) or _DEFECT_PATTERN.fullmatch(defect_id) is None:
        raise DefectClosureError("active defect ID is malformed")
    if severity not in {"P0", "P1", "P2", "P3"}:
        raise DefectClosureError(f"active defect {defect_id} severity is invalid")
    if (
        not isinstance(discovered_against, str)
        or _COMMIT_PATTERN.fullmatch(discovered_against) is None
    ):
        raise DefectClosureError(
            f"active defect {defect_id} discovery commit is malformed"
        )
    for field in ("area", "root_cause", "required_resolution"):
        if not _nonblank(entry.get(field)):
            raise DefectClosureError(f"active defect {defect_id}.{field} is malformed")
    return {field: str(entry[field]) for field in sorted(_ACTIVE_FIELDS)}


def _active_entries(payload: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    if set(payload) != {"schema_version", "certification_requires_zero", "defects"}:
        raise DefectClosureError("active-defect ledger fields are not exact")
    if payload.get("schema_version") != _ACTIVE_SCHEMA:
        raise DefectClosureError("active-defect ledger schema is unsupported")
    if payload.get("certification_requires_zero") is not True:
        raise DefectClosureError("active-defect ledger must require zero")
    defects = payload.get("defects")
    if not isinstance(defects, list):
        raise DefectClosureError("active-defect ledger must contain an array")
    entries: dict[str, dict[str, str]] = {}
    for raw_entry in defects:
        facts = _active_facts(raw_entry)
        defect_id = facts["id"]
        if defect_id in entries:
            raise DefectClosureError(f"active-defect ledger duplicates {defect_id}")
        entries[defect_id] = facts
    return entries


def reviewed_active_defects_digest(root: Path, reviewed_commit: str) -> str:
    """Return a canonical digest of every active defect fact at one reviewed commit."""

    if _COMMIT_PATTERN.fullmatch(reviewed_commit) is None or not _commit_exists(
        root, reviewed_commit
    ):
        raise DefectClosureError("reviewed active-defect commit does not exist")
    payload = _read_commit_toml(root, reviewed_commit, _ACTIVE_LEDGER_PATH)
    entries = _active_entries(payload)
    canonical = [entries[defect_id] for defect_id in sorted(entries)]
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _resolved_entries(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if set(payload) != {"schema_version", "defects"}:
        raise DefectClosureError("resolved-defect ledger fields are not exact")
    if payload.get("schema_version") != _RESOLVED_SCHEMA:
        raise DefectClosureError("resolved-defect ledger schema is unsupported")
    defects = payload.get("defects")
    if not isinstance(defects, list):
        raise DefectClosureError("resolved-defect ledger must contain an array")
    entries: dict[str, dict[str, Any]] = {}
    for raw_entry in defects:
        if not isinstance(raw_entry, dict) or set(raw_entry) != _RESOLVED_FIELDS:
            raise DefectClosureError(
                "resolved defect fields disagree with canonical schema"
            )
        defect_id = raw_entry.get("id")
        if not isinstance(defect_id, str) or _DEFECT_PATTERN.fullmatch(defect_id) is None:
            raise DefectClosureError("resolved defect ID is malformed")
        if defect_id in entries:
            raise DefectClosureError(f"resolved-defect ledger duplicates {defect_id}")
        entries[defect_id] = dict(raw_entry)
    return entries


def _record(findings: list[GovernanceFinding], code: str, message: str) -> None:
    findings.append(_finding(code, _RESOLVED_LEDGER_PATH, message))


def audit_defect_closure(
    root: Path,
    current_active: Mapping[str, Any],
    current_resolved: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Prove each resolved defect independently from immutable Git history."""

    try:
        active_now = _active_entries(current_active)
        resolved_now = _resolved_entries(current_resolved)
    except DefectClosureError as exc:
        _record(findings, "DEFECT-CLOSURE-001", str(exc))
        return

    overlap = sorted(set(active_now) & set(resolved_now))
    if overlap:
        _record(
            findings,
            "DEFECT-CLOSURE-002",
            f"defects cannot be both active and resolved: {overlap}",
        )

    for defect_id, closure in resolved_now.items():
        last_active_commit = closure.get("last_active_commit")
        resolution_commit = closure.get("resolution_commit")
        resolution_tree = closure.get("resolution_tree")
        if (
            not isinstance(last_active_commit, str)
            or _COMMIT_PATTERN.fullmatch(last_active_commit) is None
            or not _commit_exists(root, last_active_commit)
        ):
            _record(
                findings,
                "DEFECT-CLOSURE-003",
                f"resolved defect {defect_id} last-active commit does not exist",
            )
            continue
        if (
            not isinstance(resolution_commit, str)
            or _COMMIT_PATTERN.fullmatch(resolution_commit) is None
            or not _commit_exists(root, resolution_commit)
        ):
            _record(
                findings,
                "DEFECT-CLOSURE-004",
                f"resolved defect {defect_id} resolution commit does not exist",
            )
            continue
        try:
            if not _is_ancestor(root, last_active_commit, "HEAD"):
                _record(
                    findings,
                    "DEFECT-CLOSURE-005",
                    f"resolved defect {defect_id} last-active commit is outside current history",
                )
                continue
            if not _is_ancestor(root, resolution_commit, last_active_commit):
                _record(
                    findings,
                    "DEFECT-CLOSURE-006",
                    f"resolved defect {defect_id} correction was not present at its "
                    "last-active commit",
                )
                continue
        except DefectClosureError as exc:
            _record(
                findings,
                "DEFECT-CLOSURE-005",
                f"resolved defect {defect_id} ancestry cannot be verified: {exc}",
            )
            continue

        try:
            historical = _active_entries(
                _read_commit_toml(root, last_active_commit, _ACTIVE_LEDGER_PATH)
            )
        except DefectClosureError as exc:
            _record(
                findings,
                "DEFECT-CLOSURE-007",
                f"resolved defect {defect_id} cannot verify last-active facts: {exc}",
            )
            continue
        original = historical.get(defect_id)
        if original is None:
            _record(
                findings,
                "DEFECT-CLOSURE-008",
                f"resolved defect {defect_id} was not active at last_active_commit",
            )
            continue
        closure_facts = {field: closure.get(field) for field in _ACTIVE_FIELDS}
        if closure_facts != original:
            _record(
                findings,
                "DEFECT-CLOSURE-009",
                f"resolved defect {defect_id} changes its historical active facts",
            )

        if not isinstance(resolution_tree, str) or _TREE_PATTERN.fullmatch(
            resolution_tree
        ) is None:
            _record(
                findings,
                "DEFECT-CLOSURE-010",
                f"resolved defect {defect_id} resolution tree is malformed",
            )
            continue
        try:
            actual_tree = _tree_id(root, resolution_commit)
        except DefectClosureError as exc:
            _record(
                findings,
                "DEFECT-CLOSURE-010",
                f"resolved defect {defect_id} tree cannot be verified: {exc}",
            )
            continue
        if actual_tree != resolution_tree:
            _record(
                findings,
                "DEFECT-CLOSURE-011",
                f"resolved defect {defect_id} resolution tree does not match "
                "resolution_commit",
            )
