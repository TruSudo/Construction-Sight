"""Bidirectional capability, policy, dependency, and test-matrix certification."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from constructionsight.governance_certification_core import GovernanceFinding, _finding


def _tables(payload: object) -> list[Mapping[str, Any]]:
    if not isinstance(payload, list):
        return []
    return [value for value in payload if isinstance(value, dict)]


def _string_set(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item}


def audit_governance_links(
    contracts: Mapping[str, Mapping[str, Any]],
    findings: list[GovernanceFinding],
) -> None:
    """Reject missing, invented, orphaned, or authority-inconsistent references."""

    capability_path = "governance/capability_contract.toml"
    network_path = "governance/network_contract.toml"
    authorization_path = "governance/authorization_contract.toml"
    dependency_path = "governance/dependency_contract.toml"
    test_path = "governance/adversarial_test_contract.toml"

    capabilities = _tables(contracts[capability_path].get("capabilities"))
    network_policies = _tables(contracts[network_path].get("policies"))
    authorization_operations = _tables(contracts[authorization_path].get("operations"))
    dependencies = _tables(contracts[dependency_path].get("dependencies"))
    matrices = _tables(contracts[test_path].get("matrices"))

    capability_by_id = {
        str(entry["id"]): entry for entry in capabilities if isinstance(entry.get("id"), str)
    }
    network_by_id = {
        str(entry["id"]): entry for entry in network_policies if isinstance(entry.get("id"), str)
    }
    authorization_by_id = {
        str(entry["id"]): entry
        for entry in authorization_operations
        if isinstance(entry.get("id"), str)
    }
    capability_ids = set(capability_by_id)
    network_ids = set(network_by_id)
    authorization_ids = set(authorization_by_id)

    actual_network_by_capability: dict[str, set[str]] = {}
    for policy_id, policy in network_by_id.items():
        capability_id = policy.get("capability_id")
        if not isinstance(capability_id, str) or capability_id not in capability_ids:
            findings.append(
                _finding(
                    "GOV-LINK-001",
                    network_path,
                    f"network policy {policy_id} references unknown capability {capability_id}",
                )
            )
            continue
        actual_network_by_capability.setdefault(capability_id, set()).add(policy_id)
        if capability_by_id[capability_id].get("network_authority") is not True:
            findings.append(
                _finding(
                    "GOV-LINK-002",
                    network_path,
                    f"network policy {policy_id} is owned by a non-network capability",
                )
            )

    declared_network_ids: set[str] = set()
    declared_authorization_ids: set[str] = set()
    for capability_id, capability in capability_by_id.items():
        declared_network = _string_set(capability.get("network_policy_ids"))
        expected_network = actual_network_by_capability.get(capability_id, set())
        declared_network_ids.update(declared_network)
        if declared_network != expected_network:
            findings.append(
                _finding(
                    "GOV-LINK-003",
                    capability_path,
                    f"capability {capability_id} network policy linkage disagrees; "
                    f"declared={sorted(declared_network)}, expected={sorted(expected_network)}",
                )
            )
        if capability.get("network_authority") is not True and declared_network:
            findings.append(
                _finding(
                    "GOV-LINK-004",
                    capability_path,
                    f"non-network capability {capability_id} declares network policies",
                )
            )

        declared_authorization = _string_set(capability.get("authorization_operation_ids"))
        declared_authorization_ids.update(declared_authorization)
        unknown_authorization = declared_authorization - authorization_ids
        if unknown_authorization:
            findings.append(
                _finding(
                    "GOV-LINK-005",
                    capability_path,
                    f"capability {capability_id} references unknown authorization "
                    f"operations: {sorted(unknown_authorization)}",
                )
            )
        if capability.get("mutation_authority") is not True and declared_authorization:
            findings.append(
                _finding(
                    "GOV-LINK-006",
                    capability_path,
                    f"non-mutation capability {capability_id} declares authorization operations",
                )
            )

    if declared_network_ids != network_ids:
        findings.append(
            _finding(
                "GOV-LINK-007",
                capability_path,
                "network policy ownership is incomplete or invented; "
                f"declared-only={sorted(declared_network_ids - network_ids)}, "
                f"unowned={sorted(network_ids - declared_network_ids)}",
            )
        )
    if declared_authorization_ids != authorization_ids:
        findings.append(
            _finding(
                "GOV-LINK-008",
                capability_path,
                "authorization operation ownership is incomplete or invented; "
                f"declared-only={sorted(declared_authorization_ids - authorization_ids)}, "
                f"unowned={sorted(authorization_ids - declared_authorization_ids)}",
            )
        )

    for dependency in dependencies:
        name = dependency.get("name")
        referenced = _string_set(dependency.get("capabilities"))
        unknown = referenced - capability_ids
        if unknown:
            findings.append(
                _finding(
                    "GOV-LINK-009",
                    dependency_path,
                    f"dependency {name} references unknown capabilities: {sorted(unknown)}",
                )
            )

    covered_capabilities: set[str] = set()
    for matrix in matrices:
        matrix_id = matrix.get("id")
        referenced = _string_set(matrix.get("capability_ids"))
        covered_capabilities.update(referenced)
        unknown = referenced - capability_ids
        if unknown:
            findings.append(
                _finding(
                    "GOV-LINK-010",
                    test_path,
                    f"test matrix {matrix_id} references unknown capabilities: {sorted(unknown)}",
                )
            )
    uncovered = capability_ids - covered_capabilities
    if uncovered:
        findings.append(
            _finding(
                "GOV-LINK-011",
                test_path,
                f"capabilities lack adversarial test-matrix coverage: {sorted(uncovered)}",
            )
        )
