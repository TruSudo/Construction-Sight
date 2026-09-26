"""Incremental permanent defect-closure certification."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
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

_SEMANTIC_CONTRACT_PATH: Final = "governance/defect_closure_semantic_contract.toml"
_SEMANTIC_CONTRACT_SCHEMA: Final = (
    "constructionsight.defect-closure-semantic-contract/v1"
)
_SEMANTIC_PROOF_SCHEMA: Final = "constructionsight.defect-closure-proof/v1"
_SEMANTIC_PROOF_FIELDS: Final = frozenset(
    {
        "schema_version",
        "defect_id",
        "required_resolution_sha256",
        "implementation_assertions",
        "regression_assertions",
    }
)
_SEMANTIC_ASSERTION_FIELDS: Final = frozenset({"path", "operator", "value"})
_SEMANTIC_OPERATORS: Final = frozenset({"contains", "not_contains"})



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



def _read_commit_text(root: Path, commit: str, path: str) -> str:
    completed = _run_git(root, "show", f"{commit}:{path}")
    if completed.returncode != 0:
        raise DefectClosureError(
            f"cannot read {path} from {commit}: {_git_error(completed)}"
        )
    try:
        return completed.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DefectClosureError(f"{path} at {commit} is not UTF-8 text") from exc


def _read_commit_json(root: Path, commit: str, path: str) -> object:
    try:
        return json.loads(_read_commit_text(root, commit, path))
    except json.JSONDecodeError as exc:
        raise DefectClosureError(f"{path} at {commit} is malformed JSON: {exc}") from exc


def _path_exists_at_commit(root: Path, commit: str, path: str) -> bool:
    completed = _run_git(root, "cat-file", "-e", f"{commit}:{path}")
    return completed.returncode == 0


def _safe_relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise DefectClosureError("semantic proof path is malformed")
    pure = PurePosixPath(value)
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or "." in pure.parts
        or pure.as_posix() != value
    ):
        raise DefectClosureError(f"semantic proof path is unsafe: {value}")
    return value


def _path_changed_between_commits(
    root: Path,
    base_commit: str,
    head_commit: str,
    path: str,
) -> bool:
    completed = _run_git(
        root,
        "diff",
        "--quiet",
        base_commit,
        head_commit,
        "--",
        path,
    )
    if completed.returncode == 0:
        return False
    if completed.returncode == 1:
        return True
    raise DefectClosureError(
        f"cannot verify semantic evidence diff for {path}: {_git_error(completed)}"
    )


def _semantic_contract_required(root: Path, commit: str) -> bool:
    if not _path_exists_at_commit(root, commit, _SEMANTIC_CONTRACT_PATH):
        return False
    payload = _read_commit_toml(root, commit, _SEMANTIC_CONTRACT_PATH)
    if set(payload) != {"schema_version", "semantic_proof_required"}:
        raise DefectClosureError("semantic closure contract fields are not exact")
    if payload.get("schema_version") != _SEMANTIC_CONTRACT_SCHEMA:
        raise DefectClosureError("semantic closure contract schema is unsupported")
    if payload.get("semantic_proof_required") is not True:
        raise DefectClosureError("semantic closure contract must require proof")
    return True


def _semantic_proof_path(closure_evidence: object) -> str:
    path = _safe_relative_path(closure_evidence)
    pure = PurePosixPath(path)
    if pure.suffix != ".md":
        raise DefectClosureError("closure evidence must be Markdown")
    return pure.with_suffix(".proof.json").as_posix()


def _required_resolution_digest(required_resolution: str) -> str:
    return hashlib.sha256(required_resolution.encode("utf-8")).hexdigest()


def _semantic_assertions(
    proof: Mapping[str, Any],
    field: str,
) -> list[tuple[str, str, str]]:
    raw = proof.get(field)
    if not isinstance(raw, list) or not raw:
        raise DefectClosureError(f"semantic proof {field} must be nonempty")
    assertions: list[tuple[str, str, str]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != _SEMANTIC_ASSERTION_FIELDS:
            raise DefectClosureError(f"semantic proof {field} assertion is malformed")
        path = _safe_relative_path(item.get("path"))
        operator = item.get("operator")
        value = item.get("value")
        if operator not in _SEMANTIC_OPERATORS:
            raise DefectClosureError(
                f"semantic proof {field} operator is unsupported"
            )
        if not _nonblank(value):
            raise DefectClosureError(
                f"semantic proof {field} assertion value is malformed"
            )
        assertions.append((path, str(operator), str(value)))
    return assertions


def _canonical_semantic_summary(
    defect_id: str,
    required_resolution_sha256: str,
    implementation_paths: set[str],
    regression_paths: set[str],
) -> str:
    implementation = ",".join(sorted(implementation_paths))
    regressions = ",".join(sorted(regression_paths))
    return (
        f"Machine-verified closure proof for {defect_id}: "
        f"required_resolution_sha256={required_resolution_sha256}; "
        f"implementation_paths=[{implementation}]; "
        f"regression_tests=[{regressions}]."
    )


def _verify_semantic_assertion(
    *,
    content: str,
    operator: str,
    value: str,
    path: str,
) -> None:
    if operator == "contains" and value not in content:
        raise DefectClosureError(
            f"semantic proof assertion is false for {path}: missing required content"
        )
    if operator == "not_contains" and value in content:
        raise DefectClosureError(
            f"semantic proof assertion is false for {path}: forbidden content remains"
        )


def _audit_semantic_proof(
    root: Path,
    *,
    defect_id: str,
    closure: Mapping[str, Any],
    original: Mapping[str, str],
    resolution_commit: str,
    last_active_commit: str,
) -> None:
    if not _semantic_contract_required(root, resolution_commit):
        raise DefectClosureError(
            "semantic closure contract is absent from resolution_commit"
        )

    proof_path = _semantic_proof_path(closure.get("closure_evidence"))
    if not _path_exists_at_commit(root, resolution_commit, proof_path):
        raise DefectClosureError(
            f"semantic closure proof is missing at resolution_commit: {proof_path}"
        )
    if not _path_exists_at_commit(root, last_active_commit, proof_path):
        raise DefectClosureError(
            f"semantic closure proof is missing at last_active_commit: {proof_path}"
        )

    raw_proof = _read_commit_json(root, resolution_commit, proof_path)
    if not isinstance(raw_proof, dict) or set(raw_proof) != _SEMANTIC_PROOF_FIELDS:
        raise DefectClosureError("semantic closure proof fields are not exact")
    proof: Mapping[str, Any] = raw_proof
    if proof.get("schema_version") != _SEMANTIC_PROOF_SCHEMA:
        raise DefectClosureError("semantic closure proof schema is unsupported")
    if proof.get("defect_id") != defect_id:
        raise DefectClosureError("semantic closure proof defect ID does not match")

    required_resolution = original["required_resolution"]
    expected_digest = _required_resolution_digest(required_resolution)
    if proof.get("required_resolution_sha256") != expected_digest:
        raise DefectClosureError(
            "semantic closure proof does not bind the exact required resolution"
        )

    discovered_against = original["discovered_against"]
    if not _commit_exists(root, discovered_against):
        raise DefectClosureError(
            "semantic closure proof discovery commit does not exist"
        )
    if not _is_ancestor(root, discovered_against, resolution_commit):
        raise DefectClosureError(
            "semantic closure proof resolution is outside discovery history"
        )
    if not _path_changed_between_commits(
        root,
        discovered_against,
        resolution_commit,
        proof_path,
    ):
        raise DefectClosureError("semantic closure proof sidecar is not new or changed")

    implementation = _semantic_assertions(proof, "implementation_assertions")
    regressions = _semantic_assertions(proof, "regression_assertions")
    if not any(
        operator == "not_contains"
        for _path, operator, _value in implementation + regressions
    ):
        raise DefectClosureError(
            "semantic closure proof must include a negative contradiction witness"
        )

    evidence_paths = closure.get("evidence_paths")
    regression_tests = closure.get("regression_tests")
    if not isinstance(evidence_paths, list) or not all(
        isinstance(item, str) for item in evidence_paths
    ):
        raise DefectClosureError("semantic closure evidence paths are malformed")
    if not isinstance(regression_tests, list) or not all(
        isinstance(item, str) for item in regression_tests
    ):
        raise DefectClosureError("semantic closure regression tests are malformed")

    closure_evidence = _safe_relative_path(closure.get("closure_evidence"))
    if closure_evidence not in evidence_paths or proof_path not in evidence_paths:
        raise DefectClosureError(
            "semantic closure evidence must retain its narrative and proof sidecar"
        )

    implementation_paths: set[str] = set()
    for path, operator, value in implementation:
        if path.startswith("tests/"):
            raise DefectClosureError(
                f"implementation assertion cannot use a regression test: {path}"
            )
        if path not in evidence_paths:
            raise DefectClosureError(
                f"implementation assertion is not retained as evidence: {path}"
            )
        if not _path_changed_between_commits(
            root,
            discovered_against,
            resolution_commit,
            path,
        ):
            raise DefectClosureError(
                f"implementation evidence did not change after discovery: {path}"
            )
        content = _read_commit_text(root, resolution_commit, path)
        _verify_semantic_assertion(
            content=content,
            operator=operator,
            value=value,
            path=path,
        )
        implementation_paths.add(path)

    regression_paths: set[str] = set()
    for path, operator, value in regressions:
        if not path.startswith("tests/"):
            raise DefectClosureError(
                f"regression assertion must target tests/: {path}"
            )
        if path not in regression_tests:
            raise DefectClosureError(
                f"semantic regression is not listed in closure evidence: {path}"
            )
        if not _path_changed_between_commits(
            root,
            discovered_against,
            resolution_commit,
            path,
        ):
            raise DefectClosureError(
                f"regression evidence did not change after discovery: {path}"
            )
        content = _read_commit_text(root, resolution_commit, path)
        if defect_id not in content:
            raise DefectClosureError(
                f"semantic regression lacks explicit defect marker {defect_id}: {path}"
            )
        _verify_semantic_assertion(
            content=content,
            operator=operator,
            value=value,
            path=path,
        )
        regression_paths.add(path)

    expected_summary = _canonical_semantic_summary(
        defect_id,
        expected_digest,
        implementation_paths,
        regression_paths,
    )
    if closure.get("resolution_summary") != expected_summary:
        raise DefectClosureError(
            "resolution_summary is not the canonical machine-verified summary"
        )

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
            continue

        try:
            if _semantic_contract_required(root, last_active_commit):
                _audit_semantic_proof(
                    root,
                    defect_id=defect_id,
                    closure=closure,
                    original=original,
                    resolution_commit=resolution_commit,
                    last_active_commit=last_active_commit,
                )
        except DefectClosureError as exc:
            _record(
                findings,
                "DEFECT-CLOSURE-012",
                f"resolved defect {defect_id} semantic proof is invalid: {exc}",
            )
