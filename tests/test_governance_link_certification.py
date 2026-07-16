from __future__ import annotations

from copy import deepcopy
from typing import Any

from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.governance_link_certification import audit_governance_links


def _capability(
    capability_id: str,
    *,
    network: bool = False,
    mutation: bool = False,
    network_ids: list[str] | None = None,
    authorization_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "status": "implemented",
        "network_authority": network,
        "mutation_authority": mutation,
        "network_policy_ids": network_ids or [],
        "authorization_operation_ids": authorization_ids or [],
    }


def _contracts() -> dict[str, dict[str, Any]]:
    return {
        "governance/capability_contract.toml": {
            "capabilities": [
                _capability(
                    "CS-CAP-001",
                    network=True,
                    network_ids=["CS-NET-001"],
                ),
                _capability(
                    "CS-CAP-002",
                    mutation=True,
                    authorization_ids=["CS-AUTH-001"],
                ),
                _capability("CS-CAP-003"),
            ]
        },
        "governance/network_contract.toml": {
            "policies": [
                {
                    "id": "CS-NET-001",
                    "capability_id": "CS-CAP-001",
                }
            ]
        },
        "governance/authorization_contract.toml": {"operations": [{"id": "CS-AUTH-001"}]},
        "governance/dependency_contract.toml": {
            "dependencies": [{"name": "example", "capabilities": ["CS-CAP-001"]}]
        },
        "governance/adversarial_test_contract.toml": {
            "matrices": [
                {
                    "id": "CS-TEST-001",
                    "capability_ids": [
                        "CS-CAP-001",
                        "CS-CAP-002",
                        "CS-CAP-003",
                    ],
                }
            ]
        },
    }


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_bidirectional_governance_links_accept_complete_graph() -> None:
    findings: list[GovernanceFinding] = []

    audit_governance_links(_contracts(), findings)

    assert findings == []


def test_network_policy_rejects_unknown_or_non_network_capability() -> None:
    contracts = _contracts()
    policies = contracts["governance/network_contract.toml"]["policies"]
    assert isinstance(policies, list)
    policies.append(
        {
            "id": "CS-NET-002",
            "capability_id": "CS-CAP-002",
        }
    )
    policies.append(
        {
            "id": "CS-NET-003",
            "capability_id": "CS-CAP-999",
        }
    )
    findings: list[GovernanceFinding] = []

    audit_governance_links(contracts, findings)

    assert {"GOV-LINK-001", "GOV-LINK-002", "GOV-LINK-003"} <= _codes(findings)


def test_capability_rejects_invented_or_orphaned_authorization() -> None:
    contracts = _contracts()
    capabilities = contracts["governance/capability_contract.toml"]["capabilities"]
    assert isinstance(capabilities, list)
    capability = deepcopy(capabilities[1])
    assert isinstance(capability, dict)
    capability["authorization_operation_ids"] = ["CS-AUTH-999"]
    capabilities[1] = capability
    findings: list[GovernanceFinding] = []

    audit_governance_links(contracts, findings)

    assert {"GOV-LINK-005", "GOV-LINK-008"} <= _codes(findings)


def test_dependency_rejects_unknown_capability_reference() -> None:
    contracts = _contracts()
    dependencies = contracts["governance/dependency_contract.toml"]["dependencies"]
    assert isinstance(dependencies, list)
    dependency = dependencies[0]
    assert isinstance(dependency, dict)
    dependency["capabilities"] = ["CS-CAP-999"]
    findings: list[GovernanceFinding] = []

    audit_governance_links(contracts, findings)

    assert "GOV-LINK-009" in _codes(findings)


def test_every_capability_requires_adversarial_matrix_coverage() -> None:
    contracts = _contracts()
    matrices = contracts["governance/adversarial_test_contract.toml"]["matrices"]
    assert isinstance(matrices, list)
    matrix = matrices[0]
    assert isinstance(matrix, dict)
    matrix["capability_ids"] = ["CS-CAP-001", "CS-CAP-002"]
    findings: list[GovernanceFinding] = []

    audit_governance_links(contracts, findings)

    assert "GOV-LINK-011" in _codes(findings)
