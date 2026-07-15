"""Orchestrate fail-closed semantic governance certification."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from constructionsight.architecture_certification import _audit_architecture
from constructionsight.authority_certification import (
    _audit_authorization,
    _audit_defects_and_review,
    _audit_network,
    _audit_test_obligations,
)
from constructionsight.governance_certification_core import (
    SCHEMA_VERSION,
    _ARCHITECTURE_SCHEMA,
    _AUTHORIZATION_SCHEMA,
    _CAPABILITY_SCHEMA,
    _DEPENDENCY_SCHEMA,
    _NETWORK_SCHEMA,
    _TEST_SCHEMA,
    GovernanceFinding,
    GovernanceMetrics,
    GovernanceReport,
    _read_toml,
)
from constructionsight.traceability_certification import (
    _audit_capabilities,
    _audit_dependencies,
)


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

    layer_by_module, _graph, mutation_map, metrics = _audit_architecture(
        repository_root,
        tracked,
        architecture,
        network,
        findings,
    )
    capability_count = _audit_capabilities(
        repository_root,
        tracked,
        capability,
        layer_by_module,
        findings,
    )
    dependency_count = _audit_dependencies(repository_root, dependency, findings)
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
