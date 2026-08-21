"""Network, authorization, test, defect, and review certification."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from constructionsight.defect_closure_certification import audit_defect_closure
from constructionsight.governance_certification_core import (
    _ACTIVE_DEFECT_SCHEMA,
    _RESOLVED_DEFECT_SCHEMA,
    _REVIEW_SCHEMA,
    GovernanceContractError,
    GovernanceFinding,
    _finding,
    _read_toml,
)
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)
from constructionsight.traceability_certification import _match_contract_owner

_ALLOWED_AFTER_REVIEW = frozenset(
    {
        "governance/reviews/independent_review.json",
        "governance/active_defects.toml",
        "governance/resolved_defects.toml",
        "docs/audits/silent_risk_certification_2026-07-15.md",
    }
)
_REVIEW_FIELDS = frozenset(
    {
        "schema_version",
        "status",
        "reviewer",
        "review_method",
        "reviewed_commit",
        "reviewed_active_defects_digest",
        "reviewed_tree_digest",
        "findings",
    }
)
_REVIEW_TREE_DOMAIN = b"constructionsight.reviewed-tree/v1\0"


def _audit_network(contract: Mapping[str, Any], findings: list[GovernanceFinding]) -> int:
    path = "governance/network_contract.toml"
    policies = contract.get("policies")
    if not isinstance(policies, list):
        findings.append(
            _finding(
                "NET-CONTRACT-001",
                path,
                "network policies must be an array of tables",
            )
        )
        return 0
    required = {
        "id",
        "module",
        "capability_id",
        "methods",
        "hosts",
        "path_prefixes",
        "query_scope",
        "body_scope",
        "connect_timeout_seconds",
        "read_timeout_seconds",
        "write_timeout_seconds",
        "pool_timeout_seconds",
        "max_response_bytes",
        "redirect_policy",
        "media_types",
        "encodings",
        "retryable_failures",
        "terminal_failures",
        "max_attempts",
        "backoff_seconds",
        "jitter",
        "idempotency_rule",
        "rate_limit",
        "concurrency_limit",
        "circuit_breaker",
        "bulkhead",
        "cancellation",
        "partial_result",
        "evidence_retention",
        "telemetry",
        "credential_authority",
        "robots_terms_authority",
        "access_control_behavior",
        "no_bypass",
    }
    ids: set[str] = set()
    modules: set[str] = set()
    for policy in policies:
        if not isinstance(policy, dict):
            findings.append(
                _finding("NET-CONTRACT-002", path, "each network policy must be a table")
            )
            continue
        missing = required - set(policy)
        unknown = set(policy) - required
        if missing or unknown:
            findings.append(
                _finding(
                    "NET-CONTRACT-003",
                    path,
                    "network policy fields disagree with schema; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
        policy_id = str(policy.get("id"))
        module = str(policy.get("module"))
        if policy_id in ids:
            findings.append(
                _finding(
                    "NET-CONTRACT-004",
                    path,
                    f"duplicate network policy ID: {policy_id}",
                )
            )
        if module in modules:
            findings.append(
                _finding(
                    "NET-CONTRACT-005",
                    path,
                    f"module has multiple network policies: {module}",
                )
            )
        ids.add(policy_id)
        modules.add(module)
        if policy.get("no_bypass") is not True:
            findings.append(
                _finding(
                    "NET-AUTH-001",
                    path,
                    f"network policy {policy_id} must explicitly prohibit bypass",
                )
            )
        if policy.get("redirect_policy") not in {"deny", "same-host-only"}:
            findings.append(
                _finding(
                    "NET-RESILIENCE-001",
                    path,
                    f"network policy {policy_id} has unsafe redirect policy",
                )
            )
        for numeric in (
            "connect_timeout_seconds",
            "read_timeout_seconds",
            "write_timeout_seconds",
            "pool_timeout_seconds",
            "max_response_bytes",
            "max_attempts",
            "concurrency_limit",
        ):
            value = policy.get(numeric)
            if not isinstance(value, int | float) or value <= 0:
                findings.append(
                    _finding(
                        "NET-CONTRACT-006",
                        path,
                        f"network policy {policy_id}.{numeric} must be positive",
                    )
                )
        if policy.get("max_attempts", 0) > 1 and not policy.get("retryable_failures"):
            findings.append(
                _finding(
                    "NET-RETRY-001",
                    path,
                    f"network policy {policy_id} retries without classified failures",
                )
            )
    return len(policies)


def _audit_authorization(
    contract: Mapping[str, Any],
    mutation_map: Mapping[str, tuple[int, ...]],
    findings: list[GovernanceFinding],
) -> int:
    path = "governance/authorization_contract.toml"
    operations = contract.get("operations")
    if not isinstance(operations, list):
        findings.append(
            _finding(
                "AUTH-CONTRACT-001",
                path,
                "authorization operations must be an array of tables",
            )
        )
        return 0
    entries = [entry for entry in operations if isinstance(entry, dict)]
    required = {
        "id",
        "module_patterns",
        "action",
        "resource",
        "impact",
        "actor_model",
        "exact_scope",
        "current_state",
        "granted_authority",
        "denied_authority",
        "issuance",
        "validity",
        "reuse_rule",
        "revocation_rule",
        "reason_required",
        "expected_identity",
        "stale_state_rule",
        "audit_identity",
        "audit_event",
        "failure_posture",
        "boolean_confirmation_allowed",
    }
    ids: set[str] = set()
    for entry in entries:
        missing = required - set(entry)
        unknown = set(entry) - required
        if missing or unknown:
            findings.append(
                _finding(
                    "AUTH-CONTRACT-002",
                    path,
                    "authorization fields disagree with schema; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
        operation_id = str(entry.get("id"))
        if operation_id in ids:
            findings.append(
                _finding(
                    "AUTH-CONTRACT-003",
                    path,
                    f"duplicate authorization operation {operation_id}",
                )
            )
        ids.add(operation_id)
        if not entry.get("denied_authority"):
            findings.append(
                _finding(
                    "AUTH-NEGATIVE-001",
                    path,
                    f"authorization operation {operation_id} lacks negative authority",
                )
            )
        if (
            entry.get("impact") == "high"
            and entry.get("boolean_confirmation_allowed") is True
            and entry.get("actor_model") == "boolean"
        ):
            findings.append(
                _finding(
                    "AUTH-BOOLEAN-001",
                    path,
                    f"high-impact operation {operation_id} relies on a bare Boolean",
                )
            )
        if entry.get("failure_posture") != "fail-closed":
            findings.append(
                _finding(
                    "AUTH-FAIL-001",
                    path,
                    f"authorization operation {operation_id} must fail closed",
                )
            )

    for module, lines in sorted(mutation_map.items()):
        if not lines:
            continue
        module_path = Path("src", *module.split(".")).with_suffix(".py")
        if module_path.name == "__init__.py":
            continue
        owners = _match_contract_owner(
            module_path.as_posix(),
            entries,
            patterns_field="module_patterns",
            default_field="__never_default__",
            contract_path=path,
            findings=findings,
        )
        if not owners:
            findings.append(
                _finding(
                    "AUTH-CLASS-001",
                    module_path,
                    "mutation-capable module lacks an authorization classification; "
                    f"detected lines {lines}",
                    lines[0],
                )
            )
        elif len(owners) > 1:
            findings.append(
                _finding(
                    "AUTH-CLASS-002",
                    module_path,
                    "mutation-capable module matches multiple authorization operations",
                    lines[0],
                )
            )
    return len(entries)


def _audit_test_obligations(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    path = "governance/adversarial_test_contract.toml"
    matrices = contract.get("matrices")
    if not isinstance(matrices, list) or not matrices:
        findings.append(
            _finding(
                "TEST-CONTRACT-001",
                path,
                "at least one adversarial test matrix is required",
            )
        )
        return
    required_categories = set(contract.get("required_categories", []))
    if not required_categories:
        findings.append(_finding("TEST-CONTRACT-002", path, "required_categories must be nonempty"))
    ids: set[str] = set()
    for matrix in matrices:
        if not isinstance(matrix, dict):
            findings.append(_finding("TEST-CONTRACT-003", path, "each test matrix must be a table"))
            continue
        matrix_id = str(matrix.get("id"))
        if matrix_id in ids:
            findings.append(
                _finding("TEST-CONTRACT-004", path, f"duplicate test matrix {matrix_id}")
            )
        ids.add(matrix_id)
        covered = set(matrix.get("categories", []))
        excluded = matrix.get("exclusions", [])
        if not isinstance(excluded, list):
            findings.append(
                _finding(
                    "TEST-CONTRACT-005",
                    path,
                    f"{matrix_id}.exclusions must be an array",
                )
            )
            excluded = []
        justified = {
            str(item.get("category"))
            for item in excluded
            if isinstance(item, dict) and str(item.get("reason", "")).strip()
        }
        missing = required_categories - covered - justified
        if missing:
            findings.append(
                _finding(
                    "TEST-MATRIX-001",
                    path,
                    f"{matrix_id} omits categories without justification: {sorted(missing)}",
                )
            )
        tests = matrix.get("tests")
        if not isinstance(tests, list) or not tests:
            findings.append(
                _finding(
                    "TEST-MATRIX-002",
                    path,
                    f"{matrix_id} requires test artifacts",
                )
            )
            continue
        for test in tests:
            try:
                resolve_repository_file(
                    root,
                    test,
                    required_prefix="tests",
                    required_suffix=".py",
                )
            except RepositoryPathError:
                findings.append(
                    _finding(
                        "TEST-MATRIX-003",
                        path,
                        f"{matrix_id} references missing or unsafe test: {test}",
                    )
                )


def _assert_review_worktree_clean(root: Path) -> None:
    command = [
        "git",
        "-C",
        str(root),
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--",
        ".",
        *(f":(exclude){path}" for path in sorted(_ALLOWED_AFTER_REVIEW)),
    ]
    completed = subprocess.run(command, check=False, capture_output=True)
    if completed.returncode != 0:
        detail = (
            completed.stderr.decode("utf-8", errors="replace").strip()
            or completed.stdout.decode("utf-8", errors="replace").strip()
            or "unknown git error"
        )
        raise GovernanceContractError(detail)
    if completed.stdout:
        dirty = completed.stdout.replace(b"\0", b"\n").decode("utf-8", errors="replace").strip()
        raise GovernanceContractError(
            f"review-covered worktree is dirty outside permitted finalization paths: {dirty}"
        )


def _reviewed_tree_digest(root: Path) -> str:
    """Return a topology-independent digest of the clean review-covered Git index tree."""

    _assert_review_worktree_clean(root)
    completed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = (
            completed.stderr.decode("utf-8", errors="replace").strip()
            or completed.stdout.decode("utf-8", errors="replace").strip()
            or "unknown git error"
        )
        raise GovernanceContractError(detail)

    allowed = {path.encode("utf-8") for path in _ALLOWED_AFTER_REVIEW}
    entries: list[tuple[bytes, bytes, bytes]] = []
    for raw_entry in completed.stdout.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, path = raw_entry.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise GovernanceContractError("git index entry has an unexpected shape")
        mode, object_id, stage = fields
        if stage != b"0":
            display_path = path.decode("utf-8", errors="replace")
            raise GovernanceContractError(
                f"git index contains an unresolved stage for {display_path!r}"
            )
        if path in allowed:
            continue
        entries.append((path, mode, object_id))

    digest = hashlib.sha256()
    digest.update(_REVIEW_TREE_DOMAIN)
    for path, mode, object_id in sorted(entries, key=lambda entry: entry[0]):
        digest.update(len(path).to_bytes(8, byteorder="big"))
        digest.update(path)
        digest.update(b"\0")
        digest.update(mode)
        digest.update(b"\0")
        digest.update(object_id)
        digest.update(b"\0")
    return digest.hexdigest()


def _audit_defects_and_review(root: Path, findings: list[GovernanceFinding]) -> None:
    active = _read_toml(
        root,
        "governance/active_defects.toml",
        _ACTIVE_DEFECT_SCHEMA,
        findings,
    )
    defects = active.get("defects")
    if not isinstance(defects, list):
        findings.append(
            _finding(
                "DEFECT-CONTRACT-001",
                "governance/active_defects.toml",
                "defects must be an array",
            )
        )
    elif defects:
        for defect in defects:
            defect_id = defect.get("id") if isinstance(defect, dict) else "unknown"
            findings.append(
                _finding(
                    "DEFECT-ACTIVE-001",
                    "governance/active_defects.toml",
                    f"active defect blocks certification: {defect_id}",
                )
            )
    resolved = _read_toml(
        root,
        "governance/resolved_defects.toml",
        _RESOLVED_DEFECT_SCHEMA,
        findings,
    )

    review_relative = Path("governance/reviews/independent_review.json")
    try:
        _canonical, review_path = resolve_repository_file(
            root,
            review_relative.as_posix(),
            required_prefix="governance/reviews",
            required_suffix=".json",
        )
    except RepositoryPathError:
        findings.append(
            _finding(
                "REVIEW-001",
                review_relative,
                "independent adversarial review report is missing",
            )
        )
        return
    try:
        report = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        findings.append(
            _finding(
                "REVIEW-002",
                review_relative,
                f"review report is malformed: {exc}",
            )
        )
        return
    if not isinstance(report, dict):
        findings.append(
            _finding(
                "REVIEW-002",
                review_relative,
                "review report must be a JSON object",
            )
        )
        return
    missing = _REVIEW_FIELDS - set(report)
    unknown = set(report) - _REVIEW_FIELDS
    if missing or unknown:
        findings.append(
            _finding(
                "REVIEW-010",
                review_relative,
                "independent review fields disagree with schema; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}",
            )
        )
    if report.get("schema_version") != _REVIEW_SCHEMA:
        findings.append(
            _finding(
                "REVIEW-003",
                review_relative,
                "unsupported independent review schema",
            )
        )
    if report.get("status") != "passed":
        findings.append(
            _finding(
                "REVIEW-004",
                review_relative,
                "independent review has not passed",
            )
        )
    for field in ("reviewer", "review_method"):
        value = report.get(field)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            findings.append(
                _finding(
                    "REVIEW-011",
                    review_relative,
                    f"{field} must be nonblank trimmed text",
                )
            )
    review_findings = report.get("findings")
    malformed_or_unresolved = not isinstance(review_findings, list) or any(
        not isinstance(item, dict) or item.get("status") != "resolved" for item in review_findings
    )
    if malformed_or_unresolved:
        findings.append(
            _finding(
                "REVIEW-005",
                review_relative,
                "independent review contains unresolved or malformed findings",
            )
        )
    reviewed_commit = report.get("reviewed_commit")
    if not isinstance(reviewed_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", reviewed_commit):
        findings.append(
            _finding(
                "REVIEW-006",
                review_relative,
                "reviewed_commit must be a full commit SHA",
            )
        )
    reviewed_tree_digest = report.get("reviewed_tree_digest")
    if not isinstance(reviewed_tree_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", reviewed_tree_digest
    ):
        findings.append(
            _finding(
                "REVIEW-012",
                review_relative,
                "reviewed_tree_digest must be a lowercase SHA-256 digest",
            )
        )
        return
    reviewed_active_defects_digest = report.get("reviewed_active_defects_digest")
    if not isinstance(reviewed_active_defects_digest, str) or not re.fullmatch(
        r"[0-9a-f]{64}", reviewed_active_defects_digest
    ):
        findings.append(
            _finding(
                "REVIEW-013",
                review_relative,
                "reviewed_active_defects_digest must be a lowercase SHA-256 digest",
            )
        )
    try:
        current_tree_digest = _reviewed_tree_digest(root)
    except GovernanceContractError as exc:
        findings.append(
            _finding(
                "REVIEW-007",
                review_relative,
                f"cannot verify review binding: {exc}",
            )
        )
        return
    if current_tree_digest != reviewed_tree_digest:
        findings.append(
            _finding(
                "REVIEW-009",
                review_relative,
                "tracked tree outside permitted post-review governance artifacts "
                "does not match the independently reviewed tree digest",
            )
        )
    if (
        report.get("status") == "passed"
        and isinstance(reviewed_commit, str)
        and re.fullmatch(r"[0-9a-f]{40}", reviewed_commit)
        and isinstance(reviewed_active_defects_digest, str)
        and re.fullmatch(r"[0-9a-f]{64}", reviewed_active_defects_digest)
    ):
        audit_defect_closure(root, active, resolved, report, findings)
