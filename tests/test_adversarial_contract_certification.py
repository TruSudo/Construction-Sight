from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from constructionsight.adversarial_contract_certification import (
    audit_adversarial_contract,
)
from constructionsight.governance_certification_core import GovernanceFinding

_CATEGORIES = [
    "audit-failure-rollback",
    "authority-expansion-reuse-expiry",
    "boundary-overflow-excessive-size",
    "conflicting-same-time-evidence",
    "dependency-source-drift",
    "duplicates-ordering",
    "empty-absent-null-unknown-extra",
    "malformed-identity-schema",
    "oversized-malformed-terminal-access-control",
    "partial-interrupted-write-cleanup",
    "replay-conflicting-replay-idempotency",
    "retry-exhaustion-cancellation",
    "stale-concurrent-writers",
    "stale-future-naive-time",
    "tampering-hash-mismatch",
    "traversal-symlink",
    "unicode-normalization",
]


def _contract() -> dict[str, Any]:
    return {
        "schema_version": "constructionsight.adversarial-test-contract/v1",
        "contract_id": "test-adversarial",
        "required_categories": list(_CATEGORIES),
        "matrices": [
            {
                "id": "CS-TEST-001",
                "capability_ids": ["CS-CAP-001"],
                "tests": ["tests/evidence.py"],
                "categories": list(_CATEGORIES),
                "exclusions": [],
                "branch_testing": "branch obligations",
                "mutation_testing": "mutation obligations",
                "property_testing": "property obligations",
                "concurrency_testing": "concurrency obligations",
            }
        ],
    }


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_complete_adversarial_contract_passes(tmp_path: Path) -> None:
    test_path = tmp_path / "tests/evidence.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text("def test_evidence():\n    assert True\n", encoding="utf-8")
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(tmp_path, _contract(), findings)

    assert findings == []


def test_category_doctrine_cannot_contract_or_invent(tmp_path: Path) -> None:
    contract = _contract()
    contract["required_categories"] = sorted(
        set(_CATEGORIES) - {"tampering-hash-mismatch"} | {"invented-category"}
    )
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(tmp_path, contract, findings)

    assert "ADV-CATEGORY-002" in _codes(findings)


def test_matrix_rejects_unknown_fields_and_unsafe_test(tmp_path: Path) -> None:
    contract = _contract()
    matrix = contract["matrices"][0]
    assert isinstance(matrix, dict)
    matrix["unreviewed_toggle"] = True
    matrix["tests"] = ["../escape.py"]
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(tmp_path, contract, findings)

    assert {"ADV-MATRIX-003", "ADV-MATRIX-008"} <= _codes(findings)


def test_matrix_rejects_noncanonical_lists_and_missing_doctrine(
    tmp_path: Path,
) -> None:
    contract = _contract()
    matrix = contract["matrices"][0]
    assert isinstance(matrix, dict)
    matrix["capability_ids"] = ["CS-CAP-002", "CS-CAP-001"]
    matrix["categories"] = list(reversed(_CATEGORIES))
    matrix["branch_testing"] = ""
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(tmp_path, contract, findings)

    assert {
        "ADV-MATRIX-006",
        "ADV-MATRIX-009",
        "ADV-MATRIX-019",
    } <= _codes(findings)


def test_exclusion_requires_exact_fields_reason_and_no_double_count(
    tmp_path: Path,
) -> None:
    contract = deepcopy(_contract())
    matrix = contract["matrices"][0]
    assert isinstance(matrix, dict)
    matrix["exclusions"] = [
        {
            "category": "tampering-hash-mismatch",
            "reason": "",
            "unknown": True,
        }
    ]
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(tmp_path, contract, findings)

    assert {
        "ADV-MATRIX-013",
        "ADV-MATRIX-016",
        "ADV-MATRIX-017",
    } <= _codes(findings)
