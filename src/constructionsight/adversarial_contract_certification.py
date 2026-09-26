"""Strict adversarial-test matrix and mutation-backed witness certification."""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from constructionsight.governance_certification_core import GovernanceFinding, _finding
from constructionsight.repository_path_certification import (
    RepositoryPathError,
    resolve_repository_file,
)

_SCHEMA_VERSION: Final = "constructionsight.adversarial-test-contract/v2"
_REQUIRED_CATEGORIES: Final = {
    "empty-absent-null-unknown-extra",
    "malformed-identity-schema",
    "boundary-overflow-excessive-size",
    "unicode-normalization",
    "duplicates-ordering",
    "conflicting-same-time-evidence",
    "stale-future-naive-time",
    "partial-interrupted-write-cleanup",
    "replay-conflicting-replay-idempotency",
    "retry-exhaustion-cancellation",
    "stale-concurrent-writers",
    "tampering-hash-mismatch",
    "dependency-source-drift",
    "authority-expansion-reuse-expiry",
    "traversal-symlink",
    "oversized-malformed-terminal-access-control",
    "audit-failure-rollback",
}
_MATRIX_FIELDS: Final = {
    "id",
    "capability_ids",
    "tests",
    "categories",
    "witnesses",
    "exclusions",
    "branch_testing",
    "mutation_testing",
    "property_testing",
    "concurrency_testing",
}
_WITNESS_FIELDS: Final = {"category", "test", "mutation_id"}
_EXCLUSION_FIELDS: Final = {"category", "reason"}
_PYTEST_NODE: Final = re.compile(
    r"^(?P<path>tests/(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.py)"
    r"::(?P<name>test_[A-Za-z0-9_]+)$"
)


def _nonblank(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _canonical_string_list(value: object, *, nonempty: bool) -> list[str] | None:
    if not isinstance(value, list) or not all(_nonblank(item) for item in value):
        return None
    values = list(value)
    if nonempty and not values:
        return None
    if values != sorted(set(values)):
        return None
    return values


def _mutation_cases(
    mutation_contract: Mapping[str, Any],
) -> dict[str, list[Mapping[str, Any]]]:
    by_id: dict[str, list[Mapping[str, Any]]] = {}
    raw_cases = mutation_contract.get("cases")
    if not isinstance(raw_cases, list):
        return by_id
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            continue
        mutation_id_value = raw_case.get("id")
        mutation_id = mutation_id_value if isinstance(mutation_id_value, str) else ""
        if not _nonblank(mutation_id):
            continue
        by_id.setdefault(mutation_id, []).append(raw_case)
    return by_id


def _pytest_node_exists(root: Path, node: str) -> bool:
    match = _PYTEST_NODE.fullmatch(node)
    if match is None:
        return False
    raw_path = match.group("path")
    test_name = match.group("name")
    try:
        _relative, test_path = resolve_repository_file(
            root,
            raw_path,
            required_prefix="tests",
            required_suffix=".py",
        )
        tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
    except (RepositoryPathError, OSError, UnicodeError, SyntaxError):
        return False
    return any(
        isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
        and item.name == test_name
        for item in tree.body
    )


def _audit_witnesses(
    root: Path,
    *,
    matrix_label: str,
    raw_witnesses: object,
    matrix_tests: set[str],
    covered: set[str],
    required_set: set[str],
    mutation_cases: Mapping[str, list[Mapping[str, Any]]],
    used_mutations: dict[str, str],
    findings: list[GovernanceFinding],
) -> None:
    path = "governance/adversarial_test_contract.toml"
    required_witnesses = covered & required_set
    if not isinstance(raw_witnesses, list):
        findings.append(
            _finding(
                "ADV-WITNESS-001",
                path,
                f"{matrix_label} requires one mutation-backed witness per covered category",
            )
        )
        return

    witness_categories: list[str] = []
    valid_categories: set[str] = set()
    seen_categories: set[str] = set()
    for raw_witness in raw_witnesses:
        valid = True
        if not isinstance(raw_witness, dict):
            findings.append(
                _finding(
                    "ADV-WITNESS-002",
                    path,
                    f"{matrix_label} witness must be a table",
                )
            )
            continue
        missing = _WITNESS_FIELDS - set(raw_witness)
        unknown = set(raw_witness) - _WITNESS_FIELDS
        if missing or unknown:
            findings.append(
                _finding(
                    "ADV-WITNESS-002",
                    path,
                    f"{matrix_label} witness fields disagree; "
                    f"missing={sorted(missing)}, unknown={sorted(unknown)}",
                )
            )
            valid = False

        category_value = raw_witness.get("category")
        test_node_value = raw_witness.get("test")
        mutation_id_value = raw_witness.get("mutation_id")
        category = category_value if isinstance(category_value, str) else ""
        test_node = test_node_value if isinstance(test_node_value, str) else ""
        mutation_id = mutation_id_value if isinstance(mutation_id_value, str) else ""
        if (
            not _nonblank(category)
            or category not in _REQUIRED_CATEGORIES
            or category not in required_set
            or category not in covered
        ):
            findings.append(
                _finding(
                    "ADV-WITNESS-002",
                    path,
                    f"{matrix_label} witness category is invalid: {category}",
                )
            )
            valid = False
        else:
            witness_categories.append(category)
            if category in seen_categories:
                findings.append(
                    _finding(
                        "ADV-WITNESS-002",
                        path,
                        f"{matrix_label} duplicates witness category: {category}",
                    )
                )
                valid = False
            seen_categories.add(category)

        if not _nonblank(test_node) or not _pytest_node_exists(root, test_node):
            findings.append(
                _finding(
                    "ADV-WITNESS-003",
                    path,
                    f"{matrix_label} witness requires an existing exact pytest node: "
                    f"{test_node}",
                )
            )
            valid = False
        elif test_node.split("::", 1)[0] not in matrix_tests:
            findings.append(
                _finding(
                    "ADV-WITNESS-003",
                    path,
                    f"{matrix_label} witness test file is absent from matrix tests: "
                    f"{test_node}",
                )
            )
            valid = False

        if not _nonblank(mutation_id):
            findings.append(
                _finding(
                    "ADV-WITNESS-004",
                    path,
                    f"{matrix_label} witness requires a mutation ID: {category}",
                )
            )
            valid = False
        else:
            cases = mutation_cases.get(mutation_id, [])
            if len(cases) != 1:
                findings.append(
                    _finding(
                        "ADV-WITNESS-004",
                        path,
                        f"{matrix_label} witness mutation must resolve uniquely: "
                        f"{mutation_id}",
                    )
                )
                valid = False
            else:
                mutation_tests = cases[0].get("tests")
                if mutation_tests != [test_node]:
                    findings.append(
                        _finding(
                            "ADV-WITNESS-004",
                            path,
                            f"{matrix_label} witness mutation {mutation_id} must target "
                            f"only {test_node}",
                        )
                    )
                    valid = False
            prior_category = used_mutations.get(mutation_id)
            if prior_category is not None and prior_category != category:
                findings.append(
                    _finding(
                        "ADV-WITNESS-005",
                        path,
                        f"mutation {mutation_id} cannot witness both "
                        f"{prior_category} and {category}",
                    )
                )
                valid = False
            else:
                used_mutations[mutation_id] = category

        if valid:
            valid_categories.add(category)

    if witness_categories != sorted(set(witness_categories)):
        findings.append(
            _finding(
                "ADV-WITNESS-002",
                path,
                f"{matrix_label}.witnesses must be unique and sorted by category",
            )
        )

    missing_witnesses = required_witnesses - valid_categories
    if missing_witnesses:
        findings.append(
            _finding(
                "ADV-WITNESS-001",
                path,
                f"{matrix_label} lacks valid mutation-backed witnesses for: "
                f"{sorted(missing_witnesses)}",
            )
        )


def audit_adversarial_contract(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
    *,
    mutation_contract: Mapping[str, Any],
) -> None:
    """Reject incomplete, ambiguous, or non-executable adversarial-test claims."""

    path = "governance/adversarial_test_contract.toml"
    if contract.get("schema_version") != _SCHEMA_VERSION:
        findings.append(
            _finding(
                "ADV-CONTRACT-001",
                path,
                f"adversarial test contract must use {_SCHEMA_VERSION}",
            )
        )

    required = _canonical_string_list(
        contract.get("required_categories"),
        nonempty=True,
    )
    if required is None:
        findings.append(
            _finding(
                "ADV-CATEGORY-001",
                path,
                "required_categories must be nonempty, unique, sorted, and canonical",
            )
        )
        required_set: set[str] = set()
    else:
        required_set = set(required)
        missing = _REQUIRED_CATEGORIES - required_set
        invented = required_set - _REQUIRED_CATEGORIES
        if missing or invented:
            findings.append(
                _finding(
                    "ADV-CATEGORY-002",
                    path,
                    "required category doctrine disagrees with the mandatory set; "
                    f"missing={sorted(missing)}, invented={sorted(invented)}",
                )
            )

    raw_matrices = contract.get("matrices")
    if not isinstance(raw_matrices, list) or not raw_matrices:
        findings.append(
            _finding("ADV-MATRIX-001", path, "at least one test matrix is required")
        )
        return

    mutation_cases = _mutation_cases(mutation_contract)
    used_mutations: dict[str, str] = {}
    ids: set[str] = set()
    for raw in raw_matrices:
        if not isinstance(raw, dict):
            findings.append(
                _finding("ADV-MATRIX-002", path, "every test matrix must be a table")
            )
            continue
        missing_fields = _MATRIX_FIELDS - set(raw)
        unknown_fields = set(raw) - _MATRIX_FIELDS
        if missing_fields or unknown_fields:
            findings.append(
                _finding(
                    "ADV-MATRIX-003",
                    path,
                    "matrix fields disagree with schema; "
                    f"missing={sorted(missing_fields)}, unknown={sorted(unknown_fields)}",
                )
            )
        matrix_id = raw.get("id")
        if not isinstance(matrix_id, str) or not re.fullmatch(
            r"CS-TEST-[0-9]{3}", matrix_id
        ):
            findings.append(
                _finding("ADV-MATRIX-004", path, "matrix ID must match CS-TEST-NNN")
            )
            matrix_label = "unknown"
        else:
            matrix_label = matrix_id
            if matrix_id in ids:
                findings.append(
                    _finding("ADV-MATRIX-005", path, f"duplicate matrix ID: {matrix_id}")
                )
            ids.add(matrix_id)

        capability_ids = _canonical_string_list(
            raw.get("capability_ids"),
            nonempty=True,
        )
        if capability_ids is None:
            findings.append(
                _finding(
                    "ADV-MATRIX-006",
                    path,
                    f"{matrix_label}.capability_ids must be nonempty, unique, and sorted",
                )
            )

        tests = _canonical_string_list(raw.get("tests"), nonempty=True)
        matrix_tests: set[str] = set()
        if tests is None:
            findings.append(
                _finding(
                    "ADV-MATRIX-007",
                    path,
                    f"{matrix_label}.tests must be nonempty, unique, and sorted",
                )
            )
        else:
            matrix_tests = set(tests)
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
                            "ADV-MATRIX-008",
                            path,
                            f"{matrix_label} references missing or unsafe test: {test}",
                        )
                    )

        categories = _canonical_string_list(raw.get("categories"), nonempty=False)
        if categories is None:
            findings.append(
                _finding(
                    "ADV-MATRIX-009",
                    path,
                    f"{matrix_label}.categories must be unique, sorted, and canonical",
                )
            )
            covered: set[str] = set()
        else:
            covered = set(categories)
            invented = covered - _REQUIRED_CATEGORIES
            if invented:
                findings.append(
                    _finding(
                        "ADV-MATRIX-010",
                        path,
                        f"{matrix_label} declares unknown categories: {sorted(invented)}",
                    )
                )

        exclusions = raw.get("exclusions")
        excluded: set[str] = set()
        if not isinstance(exclusions, list):
            findings.append(
                _finding(
                    "ADV-MATRIX-011",
                    path,
                    f"{matrix_label}.exclusions must be an array",
                )
            )
        else:
            for exclusion in exclusions:
                if not isinstance(exclusion, dict):
                    findings.append(
                        _finding(
                            "ADV-MATRIX-012",
                            path,
                            f"{matrix_label} exclusion must be a table",
                        )
                    )
                    continue
                missing_exclusion = _EXCLUSION_FIELDS - set(exclusion)
                unknown_exclusion = set(exclusion) - _EXCLUSION_FIELDS
                if missing_exclusion or unknown_exclusion:
                    findings.append(
                        _finding(
                            "ADV-MATRIX-013",
                            path,
                            f"{matrix_label} exclusion fields disagree; "
                            f"missing={sorted(missing_exclusion)}, "
                            f"unknown={sorted(unknown_exclusion)}",
                        )
                    )
                category = exclusion.get("category")
                reason = exclusion.get("reason")
                if not _nonblank(category) or category not in _REQUIRED_CATEGORIES:
                    findings.append(
                        _finding(
                            "ADV-MATRIX-014",
                            path,
                            f"{matrix_label} exclusion category is invalid: {category}",
                        )
                    )
                    continue
                if category in excluded:
                    findings.append(
                        _finding(
                            "ADV-MATRIX-015",
                            path,
                            f"{matrix_label} duplicates exclusion: {category}",
                        )
                    )
                excluded.add(category)
                if not _nonblank(reason):
                    findings.append(
                        _finding(
                            "ADV-MATRIX-016",
                            path,
                            f"{matrix_label} exclusion requires a reason: {category}",
                        )
                    )
                if category in covered:
                    findings.append(
                        _finding(
                            "ADV-MATRIX-017",
                            path,
                            f"{matrix_label} both covers and excludes {category}",
                        )
                    )

        obligations = covered | excluded
        missing_categories = required_set - obligations
        if missing_categories:
            findings.append(
                _finding(
                    "ADV-MATRIX-018",
                    path,
                    f"{matrix_label} omits required categories: {sorted(missing_categories)}",
                )
            )

        _audit_witnesses(
            root,
            matrix_label=matrix_label,
            raw_witnesses=raw.get("witnesses"),
            matrix_tests=matrix_tests,
            covered=covered,
            required_set=required_set,
            mutation_cases=mutation_cases,
            used_mutations=used_mutations,
            findings=findings,
        )

        for field in (
            "branch_testing",
            "mutation_testing",
            "property_testing",
            "concurrency_testing",
        ):
            if not _nonblank(raw.get(field)):
                findings.append(
                    _finding(
                        "ADV-MATRIX-019",
                        path,
                        f"{matrix_label}.{field} must be nonblank trimmed doctrine",
                    )
                )
