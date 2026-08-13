from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.governance_contract_schema import (
    audit_governance_contract_shapes,
)


def _contracts() -> dict[str, dict[str, Any]]:
    return {
        "governance/architecture_contract.toml": {
            "schema_version": "constructionsight.architecture-contract/v1",
            "contract_id": "architecture-test",
            "production_root": "src/constructionsight",
            "prohibit_module_cycles": True,
            "layers": [],
        },
        "governance/capability_contract.toml": {
            "schema_version": "constructionsight.capability-contract/v1",
            "contract_id": "capability-test",
            "capabilities": [],
        },
        "governance/dependency_contract.toml": {
            "schema_version": "constructionsight.dependency-contract/v1",
            "contract_id": "dependency-test",
            "supported_python": ["3.11", "3.12"],
            "supported_runner": "github-hosted-ubuntu-x86_64",
            "lock_files": [],
            "lock_format": "pip-requirements-sha256-v1",
            "require_hashes": True,
            "binary_only": True,
            "reject_unexpected_installed_distributions": True,
            "expected_project_distribution": "constructionsight==0.1.0",
            "bootstrap_distributions": [],
            "install_policy": "exact",
            "hash_policy": "exact",
            "vulnerability_tool": "exact",
            "vulnerability_failure_policy": "fatal",
            "vulnerability_exceptions": "governance/vulnerability_exceptions.toml",
            "sbom_format": "CycloneDX 1.5 JSON",
            "sbom_output": "reports/sbom.json",
            "review_evidence": "docs/adr.md",
            "dependencies": [],
        },
        "governance/network_contract.toml": {
            "schema_version": "constructionsight.network-contract/v1",
            "contract_id": "network-test",
            "production_scheduling_authorized": False,
            "concurrent_live_integration_authorized": False,
            "policies": [],
        },
        "governance/authorization_contract.toml": {
            "schema_version": "constructionsight.authorization-contract/v1",
            "contract_id": "authorization-test",
            "hosted_identity_supported": False,
            "tenant_isolation_supported": False,
            "delegation_supported": False,
            "impersonation_supported": False,
            "temporary_elevation_supported": False,
            "operations": [],
        },
        "governance/adversarial_test_contract.toml": {
            "schema_version": "constructionsight.adversarial-test-contract/v1",
            "contract_id": "test-obligations",
            "required_categories": [],
            "matrices": [],
        },
        "governance/mutation_contract.toml": {
            "schema_version": "constructionsight.mutation-contract/v1",
            "contract_id": "mutation-test",
            "execution": "temporary overlay",
            "timeout_seconds": 120,
            "cases": [],
        },
        "governance/active_defects.toml": {
            "schema_version": "constructionsight.active-defects/v1",
            "certification_requires_zero": True,
            "defects": [],
        },
        "governance/resolved_defects.toml": {
            "schema_version": "constructionsight.resolved-defects/v1",
            "defects": [],
        },
        "governance/open_work.toml": {
            "schema_version": "constructionsight.open-work/v1",
            "overlaps": [],
        },
        "governance/vulnerability_exceptions.toml": {
            "schema_version": "constructionsight.vulnerability-exceptions/v1",
            "exceptions": [],
        },
    }


def _active_defect(defect_id: str = "CS-SR-001") -> dict[str, Any]:
    return {
        "id": defect_id,
        "severity": "P1",
        "area": "certification",
        "root_cause": "root cause",
        "discovered_against": "a" * 40,
        "required_resolution": "required resolution",
    }


def _write_resolution_evidence(root: Path, digest: str) -> None:
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "governance/reviews").mkdir(parents=True, exist_ok=True)
    (root / "docs/evidence.md").write_text("evidence\n", encoding="utf-8")
    (root / "tests/test_resolution.py").write_text(
        "def test_resolution():\n    assert True\n",
        encoding="utf-8",
    )
    (root / "governance/reviews/independent_review.json").write_text(
        json.dumps(
            {
                "schema_version": "constructionsight.independent-review/v1",
                "status": "passed",
                "reviewer": "independent-reviewer",
                "review_method": "adversarial review",
                "reviewed_commit": "c" * 40,
                "reviewed_tree_digest": digest,
                "findings": [],
            }
        ),
        encoding="utf-8",
    )


def _resolved_defect(
    defect_id: str = "CS-SR-001",
    *,
    digest: str = "d" * 64,
) -> dict[str, Any]:
    return {
        **_active_defect(defect_id),
        "resolution_summary": "Implemented and regression-tested the required correction.",
        "resolution_commit": "b" * 40,
        "evidence_paths": ["docs/evidence.md"],
        "regression_tests": ["tests/test_resolution.py"],
        "review_artifact": "governance/reviews/independent_review.json",
        "reviewed_tree_digest": digest,
    }


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_complete_contract_shapes_pass(tmp_path: Path) -> None:
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, _contracts(), findings)

    assert findings == []


def test_unknown_top_level_field_fails_closed(tmp_path: Path) -> None:
    contracts = _contracts()
    contracts["governance/network_contract.toml"]["production_schedulng_authorized"] = False
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert "GOV-SHAPE-002" in _codes(findings)


def test_future_network_or_hosted_authority_cannot_be_declared_early(
    tmp_path: Path,
) -> None:
    contracts = _contracts()
    contracts["governance/network_contract.toml"]["production_scheduling_authorized"] = True
    contracts["governance/authorization_contract.toml"]["tenant_isolation_supported"] = True
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert {"GOV-BOUNDARY-003", "GOV-BOUNDARY-004"} <= _codes(findings)


def test_active_defect_requires_exact_fields_identity_and_commit(tmp_path: Path) -> None:
    contracts = _contracts()
    contracts["governance/active_defects.toml"]["defects"] = [
        {
            "id": "bad-id",
            "severity": "urgent",
            "area": " certification ",
            "root_cause": "",
            "discovered_against": "short",
            "required_resolution": "fix",
            "unknown": True,
        }
    ]
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert {
        "GOV-LEDGER-003",
        "GOV-LEDGER-004",
        "GOV-LEDGER-006",
        "GOV-LEDGER-007",
        "GOV-LEDGER-008",
    } <= _codes(findings)


def test_valid_resolved_defect_requires_review_and_evidence(tmp_path: Path) -> None:
    digest = "d" * 64
    _write_resolution_evidence(tmp_path, digest)
    contracts = _contracts()
    contracts["governance/resolved_defects.toml"]["defects"] = [
        _resolved_defect(digest=digest)
    ]
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert findings == []


def test_resolved_defect_rejects_malformed_and_unsafe_evidence(tmp_path: Path) -> None:
    contracts = _contracts()
    malformed = _resolved_defect()
    malformed.update(
        {
            "id": "bad-id",
            "severity": "urgent",
            "area": " certification ",
            "root_cause": "",
            "discovered_against": "short",
            "required_resolution": "",
            "resolution_summary": "",
            "resolution_commit": "short",
            "evidence_paths": ["../escape"],
            "regression_tests": ["docs/not-a-test.md"],
            "review_artifact": "governance/reviews/other.json",
            "reviewed_tree_digest": "short",
            "unknown": True,
        }
    )
    contracts["governance/resolved_defects.toml"]["defects"] = [malformed]
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert {
        "GOV-RESOLVED-003",
        "GOV-RESOLVED-004",
        "GOV-RESOLVED-007",
        "GOV-RESOLVED-008",
        "GOV-RESOLVED-009",
        "GOV-RESOLVED-010",
        "GOV-RESOLVED-011",
        "GOV-RESOLVED-012",
        "GOV-RESOLVED-013",
    } <= _codes(findings)


def test_resolved_defects_reject_duplicate_and_active_overlap(tmp_path: Path) -> None:
    digest = "d" * 64
    _write_resolution_evidence(tmp_path, digest)
    resolved = _resolved_defect(digest=digest)
    contracts = _contracts()
    contracts["governance/active_defects.toml"]["defects"] = [_active_defect()]
    contracts["governance/resolved_defects.toml"]["defects"] = [
        resolved,
        deepcopy(resolved),
    ]
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert {"GOV-RESOLVED-005", "GOV-RESOLVED-006"} <= _codes(findings)


def test_resolved_defect_must_bind_canonical_review_digest(tmp_path: Path) -> None:
    _write_resolution_evidence(tmp_path, "e" * 64)
    contracts = _contracts()
    contracts["governance/resolved_defects.toml"]["defects"] = [
        _resolved_defect(digest="d" * 64)
    ]
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert "GOV-RESOLVED-015" in _codes(findings)


def test_open_work_rejects_duplicate_and_unsafe_overlap_paths(tmp_path: Path) -> None:
    overlap = {
        "repository": "TruSudo/Construction-Sight",
        "pull_request": 116,
        "head_commit": "a" * 40,
        "status": "stacked-base",
        "scope": "scope",
        "handling": "handling",
        "conflicting_paths": ["../escape", "README.md"],
    }
    contracts = _contracts()
    contracts["governance/open_work.toml"]["overlaps"] = [
        overlap,
        deepcopy(overlap),
    ]
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert {"GOV-OVERLAP-005", "GOV-OVERLAP-007"} <= _codes(findings)


def test_vulnerability_exception_requires_current_dates_and_review_evidence(
    tmp_path: Path,
) -> None:
    contracts = _contracts()
    contracts["governance/vulnerability_exceptions.toml"]["exceptions"] = [
        {
            "id": "CS-VULN-001",
            "package": "example",
            "version": "1.0",
            "advisory": "GHSA-example",
            "severity": "high",
            "owner": "owner",
            "reason": "temporary exception",
            "compensating_control": "blocked runtime path",
            "issued_on": "2020-01-01",
            "expires_on": "2020-01-02",
            "review_evidence": "docs/missing.md",
        }
    ]
    findings: list[GovernanceFinding] = []

    audit_governance_contract_shapes(tmp_path, contracts, findings)

    assert {"GOV-VULN-006", "GOV-VULN-007"} <= _codes(findings)
