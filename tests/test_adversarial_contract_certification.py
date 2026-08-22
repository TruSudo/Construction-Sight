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


def _node(index: int) -> str:
    return f"tests/evidence.py::test_witness_{index:02d}"


def _contract() -> dict[str, Any]:
    return {
        "schema_version": "constructionsight.adversarial-test-contract/v2",
        "contract_id": "test-adversarial",
        "required_categories": list(_CATEGORIES),
        "matrices": [
            {
                "id": "CS-TEST-001",
                "capability_ids": ["CS-CAP-001"],
                "tests": ["tests/evidence.py"],
                "categories": list(_CATEGORIES),
                "witnesses": [
                    {
                        "category": category,
                        "test": _node(index),
                        "mutation_id": f"TEST-MUT-{index:02d}",
                    }
                    for index, category in enumerate(_CATEGORIES, start=1)
                ],
                "exclusions": [],
                "branch_testing": "branch obligations",
                "mutation_testing": "mutation obligations",
                "property_testing": "property obligations",
                "concurrency_testing": "concurrency obligations",
            }
        ],
    }


def _mutation_contract() -> dict[str, Any]:
    return {
        "schema_version": "constructionsight.mutation-contract/v1",
        "cases": [
            {
                "id": f"TEST-MUT-{index:02d}",
                "path": "src/constructionsight/example.py",
                "search": "secure",
                "replacement": "insecure",
                "tests": [_node(index)],
                "expected_output": f"test_witness_{index:02d}",
                "risk": f"controlled risk witness for {category}",
            }
            for index, category in enumerate(_CATEGORIES, start=1)
        ],
    }


def _write_witness_tests(root: Path) -> None:
    test_path = root / "tests/evidence.py"
    test_path.parent.mkdir(parents=True)
    test_path.write_text(
        "\n\n".join(
            f"def test_witness_{index:02d}():\n    assert True"
            for index in range(1, len(_CATEGORIES) + 1)
        )
        + "\n",
        encoding="utf-8",
    )


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_complete_adversarial_contract_requires_mutation_backed_exact_nodes(
    tmp_path: Path,
) -> None:
    _write_witness_tests(tmp_path)
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(
        tmp_path,
        _contract(),
        findings,
        mutation_contract=_mutation_contract(),
    )

    assert findings == []


def test_placeholder_file_cannot_receive_category_credit(tmp_path: Path) -> None:
    _write_witness_tests(tmp_path)
    contract = _contract()
    matrix = contract["matrices"][0]
    assert isinstance(matrix, dict)
    matrix["witnesses"] = []
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(
        tmp_path,
        contract,
        findings,
        mutation_contract=_mutation_contract(),
    )

    assert "ADV-WITNESS-001" in _codes(findings)


def test_witness_mutation_must_target_exact_node_alone(tmp_path: Path) -> None:
    _write_witness_tests(tmp_path)
    mutations = _mutation_contract()
    cases = mutations["cases"]
    assert isinstance(cases, list)
    first = cases[0]
    assert isinstance(first, dict)
    first["tests"] = [_node(2)]
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(
        tmp_path,
        _contract(),
        findings,
        mutation_contract=mutations,
    )

    assert "ADV-WITNESS-004" in _codes(findings)


def test_witness_requires_existing_exact_pytest_node(tmp_path: Path) -> None:
    _write_witness_tests(tmp_path)
    contract = _contract()
    matrix = contract["matrices"][0]
    assert isinstance(matrix, dict)
    witnesses = matrix["witnesses"]
    assert isinstance(witnesses, list)
    first = witnesses[0]
    assert isinstance(first, dict)
    first["test"] = "tests/evidence.py::test_missing"
    mutations = _mutation_contract()
    cases = mutations["cases"]
    assert isinstance(cases, list)
    mutation = cases[0]
    assert isinstance(mutation, dict)
    mutation["tests"] = ["tests/evidence.py::test_missing"]
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(
        tmp_path,
        contract,
        findings,
        mutation_contract=mutations,
    )

    assert "ADV-WITNESS-003" in _codes(findings)


def test_witness_mutations_cannot_be_reused_across_categories(tmp_path: Path) -> None:
    _write_witness_tests(tmp_path)
    contract = _contract()
    matrix = contract["matrices"][0]
    assert isinstance(matrix, dict)
    witnesses = matrix["witnesses"]
    assert isinstance(witnesses, list)
    first = witnesses[0]
    second = witnesses[1]
    assert isinstance(first, dict)
    assert isinstance(second, dict)
    second["mutation_id"] = first["mutation_id"]
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(
        tmp_path,
        contract,
        findings,
        mutation_contract=_mutation_contract(),
    )

    assert "ADV-WITNESS-005" in _codes(findings)


def test_category_doctrine_cannot_contract_or_invent(tmp_path: Path) -> None:
    contract = _contract()
    contract["required_categories"] = sorted(
        set(_CATEGORIES) - {"tampering-hash-mismatch"} | {"invented-category"}
    )
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(
        tmp_path,
        contract,
        findings,
        mutation_contract=_mutation_contract(),
    )

    assert "ADV-CATEGORY-002" in _codes(findings)


def test_matrix_rejects_unknown_fields_and_unsafe_test(tmp_path: Path) -> None:
    contract = _contract()
    matrix = contract["matrices"][0]
    assert isinstance(matrix, dict)
    matrix["unreviewed_toggle"] = True
    matrix["tests"] = ["../escape.py"]
    findings: list[GovernanceFinding] = []

    audit_adversarial_contract(
        tmp_path,
        contract,
        findings,
        mutation_contract=_mutation_contract(),
    )

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

    audit_adversarial_contract(
        tmp_path,
        contract,
        findings,
        mutation_contract=_mutation_contract(),
    )

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

    audit_adversarial_contract(
        tmp_path,
        contract,
        findings,
        mutation_contract=_mutation_contract(),
    )

    assert {
        "ADV-MATRIX-013",
        "ADV-MATRIX-016",
        "ADV-MATRIX-017",
    } <= _codes(findings)
