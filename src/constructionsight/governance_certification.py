"""Orchestrate fail-closed semantic governance certification."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from constructionsight.adversarial_contract_certification import (
    audit_adversarial_contract,
)
from constructionsight.architecture_certification import _audit_architecture
from constructionsight.authority_certification import (
    _audit_authorization,
    _audit_defects_and_review,
    _audit_network,
    _audit_test_obligations,
)
from constructionsight.dependency_certification import (
    audit_dependencies,
    audit_dependency_agreement,
)
from constructionsight.governance_certification_core import (
    SCHEMA_VERSION,
    _ACTIVE_DEFECT_SCHEMA,
    _ARCHITECTURE_SCHEMA,
    _AUTHORIZATION_SCHEMA,
    _CAPABILITY_SCHEMA,
    _DEPENDENCY_SCHEMA,
    _NETWORK_SCHEMA,
    _RESOLVED_DEFECT_SCHEMA,
    _TEST_SCHEMA,
    GovernanceFinding,
    GovernanceMetrics,
    GovernanceReport,
    _read_toml,
)
from constructionsight.governance_contract_schema import (
    audit_governance_contract_shapes,
)
from constructionsight.governance_link_certification import audit_governance_links
from constructionsight.semantic_authorization_certification import (
    audit_semantic_authorization,
)
from constructionsight.traceability_certification import _audit_capabilities

_MUTATION_SCHEMA = "constructionsight.mutation-contract/v1"
_OPEN_WORK_SCHEMA = "constructionsight.open-work/v1"
_VULNERABILITY_EXCEPTION_SCHEMA = "constructionsight.vulnerability-exceptions/v1"


def audit_governance(root: Path, tracked_files: Sequence[Path]) -> GovernanceReport:
    """Audit semantic governance for one exact tracked tree."""

    repository_root = root.resolve()
    tracked = tuple(sorted((Path(value) for value in tracked_files), key=Path.as_posix))
    findings: list[GovernanceFinding] = []
    architecture = _read_toml(
        repository_root,
        "governance/architecture_contract.toml",
        _ARCHITECTURE_SCHEMA,
        findings,
    )
    capability = _read_toml(
        repository_root,
        "governance/capability_contract.toml",
        _CAPABILITY_SCHEMA,
        findings,
    )
    dependency = _read_toml(
        repository_root,
        "governance/dependency_contract.toml",
        _DEPENDENCY_SCHEMA,
        findings,
    )
    network = _read_toml(
        repository_root,
        "governance/network_contract.toml",
        _NETWORK_SCHEMA,
        findings,
    )
    authorization = _read_toml(
        repository_root,
        "governance/authorization_contract.toml",
        _AUTHORIZATION_SCHEMA,
        findings,
    )
    tests = _read_toml(
        repository_root,
        "governance/adversarial_test_contract.toml",
        _TEST_SCHEMA,
        findings,
    )
    mutation = _read_toml(
        repository_root,
        "governance/mutation_contract.toml",
        _MUTATION_SCHEMA,
        findings,
    )
    active_defects = _read_toml(
        repository_root,
        "governance/active_defects.toml",
        _ACTIVE_DEFECT_SCHEMA,
        findings,
    )
    resolved_defects = _read_toml(
        repository_root,
        "governance/resolved_defects.toml",
        _RESOLVED_DEFECT_SCHEMA,
        findings,
    )
    open_work = _read_toml(
        repository_root,
        "governance/open_work.toml",
        _OPEN_WORK_SCHEMA,
        findings,
    )
    vulnerability_exceptions = _read_toml(
        repository_root,
        "governance/vulnerability_exceptions.toml",
        _VULNERABILITY_EXCEPTION_SCHEMA,
        findings,
    )
    contracts = {
        "governance/architecture_contract.toml": architecture,
        "governance/capability_contract.toml": capability,
        "governance/dependency_contract.toml": dependency,
        "governance/network_contract.toml": network,
        "governance/authorization_contract.toml": authorization,
        "governance/adversarial_test_contract.toml": tests,
        "governance/mutation_contract.toml": mutation,
        "governance/active_defects.toml": active_defects,
        "governance/resolved_defects.toml": resolved_defects,
        "governance/open_work.toml": open_work,
        "governance/vulnerability_exceptions.toml": vulnerability_exceptions,
    }
    audit_governance_contract_shapes(repository_root, contracts, findings)
    audit_governance_links(contracts, findings)
    audit_adversarial_contract(repository_root, tests, findings)

    layer_by_module, _graph, mutation_map, metrics = _audit_architecture(
        repository_root,
        tracked,
        architecture,
        network,
        findings,
    )
    audit_semantic_authorization(
        repository_root,
        tracked,
        layer_by_module,
        findings,
    )
    capability_count = _audit_capabilities(
        repository_root,
        tracked,
        capability,
        layer_by_module,
        findings,
    )
    dependency_count = audit_dependencies(repository_root, dependency, findings)
    audit_dependency_agreement(repository_root, dependency, findings)
    network_count = _audit_network(network, findings)
    authorization_count = _audit_authorization(
        authorization,
        mutation_map,
        findings,
    )
    _audit_test_obligations(repository_root, tests, findings)
    _audit_defects_and_review(repository_root, findings)

    ordered = tuple(
        sorted(
            findings,
            key=lambda item: (item.code, item.path, item.line or 0, item.message),
        )
    )
    final_metrics = GovernanceMetrics(
        architecture_nodes=metrics.architecture_nodes,
        architecture_edges=metrics.architecture_edges,
        architecture_cycles=metrics.architecture_cycles,
        capability_count=capability_count,
        dependency_count=dependency_count,
        network_policy_count=network_count,
        authorization_operation_count=authorization_count,
    )
    return GovernanceReport(
        schema_version=SCHEMA_VERSION,
        finding_count=len(ordered),
        findings=ordered,
        metrics=final_metrics,
    )
