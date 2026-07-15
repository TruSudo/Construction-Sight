"""Network, authorization, test, defect, and review certification."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from constructionsight.governance_certification_core import (
    _ACTIVE_DEFECT_SCHEMA,
    _RESOLVED_DEFECT_SCHEMA,
    _REVIEW_SCHEMA,
    GovernanceContractError,
    GovernanceFinding,
    _finding,
    _git,
    _read_toml,
)
from constructionsight.traceability_certification import _match_contract_owner


def _audit_network(
    contract: Mapping[str, Any], findings: list[GovernanceFinding]
) -> int:
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
            if not isinstance(value, (int, float)) or value <= 0:
                findings.append(
                    _finding(
                        "NET-CONTRACT-006",
                        path,
                        f"network policy {policy_id}.{numeric} must be positive",
                    )
                )
        if policy.get("max_attempts", 0) > 1 and not policy.get(
            "retryable_failures"
        ):
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
        findings.append(
            _finding("TEST-CONTRACT-002", path, "required_categories must be nonempty")
        )
    ids: set[str] = set()
    for matrix in matrices:
        if not isinstance(matrix, dict):
            findings.append(
                _finding("TEST-CONTRACT-003", path, "each test matrix must be a table")
            )
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
                    f"{matrix_id} omits categories without justification: "
                    f"{sorted(missing)}",
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
            if not isinstance(test, str) or not (root / test).is_file():
                findings.append(
                    _finding(
                        "TEST-MATRIX-003",
                        path,
                        f"{matrix_id} references missing test: {test}",
                    )
                )


def _audit_defects_and_review(
    root: Path, findings: list[GovernanceFinding]
) -> None:
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
    _read_toml(
        root,
        "governance/resolved_defects.toml",
        _RESOLVED_DEFECT_SCHEMA,
        findings,
    )

    review_path = root / "governance/reviews/independent_review.json"
    if not review_path.is_file():
        findings.append(
            _finding(
                "REVIEW-001",
                review_path.relative_to(root),
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
                review_path.relative_to(root),
                f"review report is malformed: {exc}",
            )
        )
        return
    if report.get("schema_version") != _REVIEW_SCHEMA:
        findings.append(
            _finding(
                "REVIEW-003",
                review_path.relative_to(root),
                "unsupported independent review schema",
            )
        )
    if report.get("status") != "passed":
        findings.append(
            _finding(
                "REVIEW-004",
                review_path.relative_to(root),
                "independent review has not passed",
            )
        )
    review_findings = report.get("findings")
    malformed_or_unresolved = (
        not isinstance(review_findings, list)
        or any(
            not isinstance(item, dict) or item.get("status") != "resolved"
            for item in review_findings
        )
    )
    if malformed_or_unresolved:
        findings.append(
            _finding(
                "REVIEW-005",
                review_path.relative_to(root),
                "independent review contains unresolved or malformed findings",
            )
        )
    reviewed_commit = report.get("reviewed_commit")
    if not isinstance(reviewed_commit, str) or not re.fullmatch(
        r"[0-9a-f]{40}", reviewed_commit
    ):
        findings.append(
            _finding(
                "REVIEW-006",
                review_path.relative_to(root),
                "reviewed_commit must be a full commit SHA",
            )
        )
        return
    try:
        head_parent = _git(root, "rev-parse", "HEAD^")
        changed = set(
            _git(root, "diff", "--name-only", f"{reviewed_commit}..HEAD").splitlines()
        )
    except GovernanceContractError as exc:
        findings.append(
            _finding(
                "REVIEW-007",
                review_path.relative_to(root),
                f"cannot verify review binding: {exc}",
            )
        )
        return
    allowed_after_review = {
        "governance/reviews/independent_review.json",
        "governance/active_defects.toml",
        "governance/resolved_defects.toml",
        "docs/audits/silent_risk_certification_2026-07-15.md",
    }
    if head_parent != reviewed_commit:
        findings.append(
            _finding(
                "REVIEW-008",
                review_path.relative_to(root),
                "reviewed_commit must be the direct parent of the exact certified head",
            )
        )
    unreviewed = changed - allowed_after_review
    if unreviewed:
        findings.append(
            _finding(
                "REVIEW-009",
                review_path.relative_to(root),
                f"unreviewed files changed after reviewed commit: {sorted(unreviewed)}",
            )
        )
