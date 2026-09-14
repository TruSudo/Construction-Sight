from __future__ import annotations

from pathlib import Path

from constructionsight.governance_certification import _merge_mutation_contracts
from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.mutation_certification import _load_contract


def _case(case_id: str) -> dict[str, object]:
    return {
        "id": case_id,
        "path": "src/constructionsight/assurance_certification.py",
        "search": "needle",
        "replacement": "replacement",
        "tests": ["tests/test_assurance_certification.py::test_native_maximum_complete_evidence_passes"],
        "expected_output": "test_native_maximum_complete_evidence_passes",
        "risk": "test risk",
    }


def _contract(*case_ids: str) -> dict[str, object]:
    return {
        "schema_version": "constructionsight.mutation-contract/v1",
        "contract_id": "test-contract",
        "execution": "overlay",
        "timeout_seconds": 120,
        "cases": [_case(case_id) for case_id in case_ids],
    }


def test_mutation_runner_loads_assurance_overlay_as_one_unique_case_set() -> None:
    _timeout, cases = _load_contract(Path.cwd())
    ids = [case.id for case in cases]

    assert len(ids) == len(set(ids))
    assert ids.count("CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001") == 1
    assert {
        "CS-MUT-ASSURANCE-CONTEXT-AGGREGATION-001",
        "CS-MUT-ASSURANCE-SOURCE-COMMIT-001",
        "CS-MUT-ASSURANCE-SOURCE-DIGEST-001",
        "CS-MUT-ASSURANCE-SOURCE-PLACEHOLDER-001",
        "CS-MUT-ASSURANCE-SOURCE-REUSE-001",
    } <= set(ids)


def test_governance_merge_accepts_only_declared_assurance_override() -> None:
    primary = _contract(
        "CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001",
        "CS-MUT-PRIMARY-001",
    )
    supplement = _contract(
        "CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001",
        "CS-MUT-ASSURANCE-SOURCE-DIGEST-001",
    )
    findings: list[GovernanceFinding] = []

    merged = _merge_mutation_contracts(primary, supplement, findings)

    assert findings == []
    cases = merged["cases"]
    assert isinstance(cases, list)
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids)) == 3


def test_governance_merge_rejects_undeclared_duplicate_case_id() -> None:
    primary = _contract(
        "CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001",
        "CS-MUT-PRIMARY-001",
    )
    supplement = _contract(
        "CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001",
        "CS-MUT-PRIMARY-001",
    )
    findings: list[GovernanceFinding] = []

    _merge_mutation_contracts(primary, supplement, findings)

    assert "GOV-MUTATION-007" in {finding.code for finding in findings}


def test_governance_merge_rejects_execution_or_timeout_drift() -> None:
    primary = _contract("CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001")
    supplement = _contract("CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001")
    supplement["execution"] = "different"
    supplement["timeout_seconds"] = 121
    findings: list[GovernanceFinding] = []

    _merge_mutation_contracts(primary, supplement, findings)

    codes = {finding.code for finding in findings}
    assert "GOV-MUTATION-004" in codes
