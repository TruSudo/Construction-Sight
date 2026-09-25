"""Immutable reviewed-defect facts and resolution-ancestry certification."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from constructionsight.governance_certification_core import (
    GovernanceFinding,
    _finding,
)

_ACTIVE_LEDGER_PATH: Final = "governance/active_defects.toml"
_RESOLVED_LEDGER_PATH: Final = "governance/resolved_defects.toml"
_ACTIVE_SCHEMA: Final = "constructionsight.active-defects/v1"
_RESOLVED_SCHEMA: Final = "constructionsight.resolved-defects/v1"
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
_ACTIVE_DIGEST_DOMAIN: Final = b"constructionsight.reviewed-active-defects/v1\0"
_COMMIT_PATTERN: Final = re.compile(r"[0-9a-f]{40}")
_DEFECT_PATTERN: Final = re.compile(r"CS-SR-[0-9]{3}")


class DefectClosureError(ValueError):
    """Raised when reviewed Git history cannot provide canonical defect facts."""


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


def _read_commit_toml(
    root: Path,
    commit: str,
    path: str,
) -> Mapping[str, Any]:
    completed = _run_git(root, "show", f"{commit}:{path}")
    if completed.returncode != 0:
        raise DefectClosureError(
            f"cannot read {path} from reviewed commit: {_git_error(completed)}"
        )
    try:
        text = completed.stdout.decode("utf-8")
        payload = tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise DefectClosureError(f"reviewed {path} is malformed: {exc}") from exc
    return payload


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _active_facts(entry: object) -> dict[str, str]:
    if not isinstance(entry, dict) or set(entry) != _ACTIVE_FIELDS:
        raise DefectClosureError("reviewed active defect fields disagree with the canonical schema")
    defect_id = entry.get("id")
    severity = entry.get("severity")
    discovered_against = entry.get("discovered_against")
    if not isinstance(defect_id, str) or _DEFECT_PATTERN.fullmatch(defect_id) is None:
        raise DefectClosureError("reviewed active defect ID is malformed")
    if severity not in {"P0", "P1", "P2", "P3"}:
        raise DefectClosureError(f"reviewed active defect {defect_id} severity is invalid")
    if (
        not isinstance(discovered_against, str)
        or _COMMIT_PATTERN.fullmatch(discovered_against) is None
    ):
        raise DefectClosureError(
            f"reviewed active defect {defect_id} discovery commit is malformed"
        )
    for field in ("area", "root_cause", "required_resolution"):
        if not _nonblank(entry.get(field)):
            raise DefectClosureError(f"reviewed active defect {defect_id}.{field} is malformed")
    return {field: str(entry[field]) for field in sorted(_ACTIVE_FIELDS)}


def _reviewed_active_entries(payload: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    if set(payload) != {"schema_version", "certification_requires_zero", "defects"}:
        raise DefectClosureError("reviewed active-defect ledger fields are not exact")
    if payload.get("schema_version") != _ACTIVE_SCHEMA:
        raise DefectClosureError("reviewed active-defect ledger schema is unsupported")
    if payload.get("certification_requires_zero") is not True:
        raise DefectClosureError(
            "reviewed active-defect ledger must require zero for certification"
        )
    defects = payload.get("defects")
    if not isinstance(defects, list):
        raise DefectClosureError("reviewed active-defect ledger must contain an array")
    entries: dict[str, dict[str, str]] = {}
    for raw_entry in defects:
        facts = _active_facts(raw_entry)
        defect_id = facts["id"]
        if defect_id in entries:
            raise DefectClosureError(f"reviewed active-defect ledger duplicates {defect_id}")
        entries[defect_id] = facts
    return entries


def _reviewed_resolved_entries(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if set(payload) != {"schema_version", "defects"}:
        raise DefectClosureError("reviewed resolved-defect ledger fields are not exact")
    if payload.get("schema_version") != _RESOLVED_SCHEMA:
        raise DefectClosureError("reviewed resolved-defect ledger schema is unsupported")
    defects = payload.get("defects")
    if not isinstance(defects, list):
        raise DefectClosureError("reviewed resolved-defect ledger must contain an array")
    entries: dict[str, dict[str, Any]] = {}
    for raw_entry in defects:
        if not isinstance(raw_entry, dict):
            raise DefectClosureError("reviewed resolved defects must be tables")
        defect_id = raw_entry.get("id")
        if not isinstance(defect_id, str) or _DEFECT_PATTERN.fullmatch(defect_id) is None:
            raise DefectClosureError("reviewed resolved defect ID is malformed")
        if defect_id in entries:
            raise DefectClosureError(f"reviewed resolved-defect ledger duplicates {defect_id}")
        entries[defect_id] = dict(raw_entry)
    return entries


def _active_digest(entries: Mapping[str, Mapping[str, str]]) -> str:
    canonical = {
        "schema_version": _ACTIVE_SCHEMA,
        "certification_requires_zero": True,
        "defects": [entries[defect_id] for defect_id in sorted(entries)],
    }
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(_ACTIVE_DIGEST_DOMAIN)
    digest.update(encoded)
    return digest.hexdigest()


def reviewed_active_defects_digest(root: Path, reviewed_commit: str) -> str:
    """Digest the complete canonical active-defect facts at one reviewed commit."""

    if _COMMIT_PATTERN.fullmatch(reviewed_commit) is None:
        raise DefectClosureError("reviewed commit must be a full lowercase commit SHA")
    if not _commit_exists(root, reviewed_commit):
        raise DefectClosureError("reviewed commit does not exist as a commit object")
    payload = _read_commit_toml(root, reviewed_commit, _ACTIVE_LEDGER_PATH)
    return _active_digest(_reviewed_active_entries(payload))


def _current_entries(
    payload: Mapping[str, Any],
    *,
    label: str,
) -> dict[str, dict[str, Any]]:
    defects = payload.get("defects")
    if not isinstance(defects, list):
        raise DefectClosureError(f"current {label} ledger must contain an array")
    entries: dict[str, dict[str, Any]] = {}
    for raw_entry in defects:
        if not isinstance(raw_entry, dict):
            raise DefectClosureError(f"current {label} defects must be tables")
        defect_id = raw_entry.get("id")
        if not isinstance(defect_id, str) or _DEFECT_PATTERN.fullmatch(defect_id) is None:
            raise DefectClosureError(f"current {label} defect ID is malformed")
        if defect_id in entries:
            raise DefectClosureError(f"current {label} ledger duplicates {defect_id}")
        entries[defect_id] = dict(raw_entry)
    return entries


def _record(
    findings: list[GovernanceFinding],
    code: str,
    message: str,
) -> None:
    findings.append(_finding(code, _RESOLVED_LEDGER_PATH, message))


def audit_defect_closure(
    root: Path,
    current_active: Mapping[str, Any],
    current_resolved: Mapping[str, Any],
    review_report: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Bind final closure records to reviewed facts and reviewed Git history."""

    reviewed_commit = review_report.get("reviewed_commit")
    reviewed_digest = review_report.get("reviewed_active_defects_digest")
    if not isinstance(reviewed_commit, str) or _COMMIT_PATTERN.fullmatch(reviewed_commit) is None:
        return
    if (
        not isinstance(reviewed_digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", reviewed_digest) is None
    ):
        return
    if not _commit_exists(root, reviewed_commit):
        _record(
            findings,
            "DEFECT-REVIEW-001",
            "reviewed implementation commit does not exist as a commit object",
        )
        return
    try:
        if not _is_ancestor(root, reviewed_commit, "HEAD"):
            _record(
                findings,
                "DEFECT-REVIEW-002",
                "reviewed implementation commit is not an ancestor of the current head",
            )
    except DefectClosureError as exc:
        _record(findings, "DEFECT-REVIEW-002", str(exc))
        return

    try:
        reviewed_active = _reviewed_active_entries(
            _read_commit_toml(root, reviewed_commit, _ACTIVE_LEDGER_PATH)
        )
        reviewed_resolved = _reviewed_resolved_entries(
            _read_commit_toml(root, reviewed_commit, _RESOLVED_LEDGER_PATH)
        )
    except DefectClosureError as exc:
        _record(findings, "DEFECT-REVIEW-003", str(exc))
        return
    if _active_digest(reviewed_active) != reviewed_digest:
        _record(
            findings,
            "DEFECT-REVIEW-004",
            "review artifact does not bind the complete active-defect facts from "
            "the reviewed implementation commit",
        )

    try:
        active_now = _current_entries(current_active, label="active-defect")
        resolved_now = _current_entries(current_resolved, label="resolved-defect")
    except DefectClosureError as exc:
        _record(findings, "DEFECT-CLOSURE-001", str(exc))
        return

    expected_resolved_ids = set(reviewed_active) | set(reviewed_resolved)
    if active_now or set(resolved_now) != expected_resolved_ids:
        missing = sorted(expected_resolved_ids - set(resolved_now))
        unexpected = sorted(set(resolved_now) - expected_resolved_ids)
        _record(
            findings,
            "DEFECT-CLOSURE-002",
            "finalization does not account exactly for every reviewed defect ID; "
            f"active={sorted(active_now)}, missing={missing}, unexpected={unexpected}",
        )

    for defect_id, original in reviewed_active.items():
        closure = resolved_now.get(defect_id)
        if closure is None:
            continue
        closure_facts = {field: closure.get(field) for field in _ACTIVE_FIELDS}
        if closure_facts != original:
            _record(
                findings,
                "DEFECT-CLOSURE-003",
                f"resolved defect {defect_id} changes reviewed original facts",
            )

    for defect_id, original in reviewed_resolved.items():
        if resolved_now.get(defect_id) != original:
            _record(
                findings,
                "DEFECT-CLOSURE-004",
                f"previously resolved defect {defect_id} changed after review",
            )

    for defect_id, closure in resolved_now.items():
        resolution_commit = closure.get("resolution_commit")
        if (
            not isinstance(resolution_commit, str)
            or _COMMIT_PATTERN.fullmatch(resolution_commit) is None
            or not _commit_exists(root, resolution_commit)
        ):
            _record(
                findings,
                "DEFECT-CLOSURE-005",
                f"resolved defect {defect_id} resolution commit does not exist",
            )
            continue
        try:
            ancestor = _is_ancestor(root, resolution_commit, reviewed_commit)
        except DefectClosureError as exc:
            _record(
                findings,
                "DEFECT-CLOSURE-006",
                f"resolved defect {defect_id} ancestry cannot be verified: {exc}",
            )
            continue
        if not ancestor:
            _record(
                findings,
                "DEFECT-CLOSURE-006",
                f"resolved defect {defect_id} resolution commit is not an ancestor "
                "of the reviewed implementation commit",
            )
