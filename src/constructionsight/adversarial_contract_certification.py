"""Strict adversarial-test matrix and category certification."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

from constructionsight.governance_certification_core import GovernanceFinding, _finding

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
    "exclusions",
    "branch_testing",
    "mutation_testing",
    "property_testing",
    "concurrency_testing",
}
_EXCLUSION_FIELDS: Final = {"category", "reason"}


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


def audit_adversarial_contract(
    root: Path,
    contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Reject incomplete, ambiguous, invented, or noncanonical test obligations."""

    path = "governance/adversarial_test_contract.toml"
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
        if tests is None:
            findings.append(
                _finding(
                    "ADV-MATRIX-007",
                    path,
                    f"{matrix_label}.tests must be nonempty, unique, and sorted",
                )
            )
        else:
            for test in tests:
                relative = Path(test)
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or relative.parts[:1] != ("tests",)
                    or not (root / relative).is_file()
                ):
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
