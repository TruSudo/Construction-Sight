"""Orchestrate fail-closed semantic governance certification."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from constructionsight.adversarial_contract_certification import (
    audit_adversarial_contract,
)
from constructionsight.architecture_boundary_certification import (
    audit_architecture_boundaries,
)
from constructionsight.architecture_certification import _audit_architecture
from constructionsight.assurance_certification import (
    _ASSURED_TREE_DOMAIN,
    CANONICAL_ASSURANCE_ARTIFACT,
    _allowed_after_assurance,
)
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
    _ACTIVE_DEFECT_SCHEMA,
    _ARCHITECTURE_SCHEMA,
    _ASSURANCE_CONTRACT_SCHEMA,
    _AUTHORIZATION_SCHEMA,
    _CAPABILITY_SCHEMA,
    _DEPENDENCY_SCHEMA,
    _NETWORK_SCHEMA,
    _RESOLVED_DEFECT_SCHEMA,
    SCHEMA_VERSION,
    GovernanceFinding,
    GovernanceMetrics,
    GovernanceReport,
    _finding,
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

_ADVERSARIAL_TEST_SCHEMA = "constructionsight.adversarial-test-contract/v2"
_MUTATION_SCHEMA = "constructionsight.mutation-contract/v1"
_MUTATION_SUPPLEMENT_PATH = "governance/mutation_contract_assurance.toml"
_MUTATION_FIELDS: Final = frozenset(
    {"schema_version", "contract_id", "execution", "timeout_seconds", "cases"}
)
_MUTATION_OVERRIDES: Final = frozenset(
    {"CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001"}
)
_OPEN_WORK_SCHEMA = "constructionsight.open-work/v1"
_VULNERABILITY_EXCEPTION_SCHEMA = "constructionsight.vulnerability-exceptions/v1"
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


def _assured_commit_tree_digest(root: Path, commit: str) -> str:
    """Digest one committed assurance-covered tree with canonical Git identities."""

    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "-z", "--full-tree", commit],
            check=False,
            capture_output=True,
        )
    except OSError as exc:
        raise ValueError(f"cannot execute git for reviewed-tree binding: {exc}") from exc
    if completed.returncode != 0:
        error = (
            completed.stderr.decode("utf-8", errors="replace").strip()
            or completed.stdout.decode("utf-8", errors="replace").strip()
            or "unknown git error"
        )
        raise ValueError(f"cannot enumerate reviewed commit tree: {error}")

    entries: list[tuple[bytes, bytes, bytes]] = []
    for raw_entry in completed.stdout.split(b"\0"):
        if not raw_entry:
            continue
        metadata, separator, path = raw_entry.partition(b"\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise ValueError("reviewed commit tree entry has an unexpected shape")
        mode, object_type, object_id = fields
        if object_type not in {b"blob", b"commit"}:
            raise ValueError("reviewed commit tree contains an unsupported object type")
        if _allowed_after_assurance(path):
            continue
        entries.append((path, mode, object_id))

    digest = hashlib.sha256()
    digest.update(_ASSURED_TREE_DOMAIN)
    for path, mode, object_id in sorted(entries, key=lambda entry: entry[0]):
        digest.update(len(path).to_bytes(8, byteorder="big"))
        digest.update(path)
        digest.update(b"\0")
        digest.update(mode)
        digest.update(b"\0")
        digest.update(object_id)
        digest.update(b"\0")
    return digest.hexdigest()


def _audit_assurance_reviewed_tree_binding(
    root: Path,
    findings: list[GovernanceFinding],
) -> None:
    """Prove assurance evidence and the reviewed commit describe one covered tree."""

    report_path = root / CANONICAL_ASSURANCE_ARTIFACT
    if not report_path.is_file():
        return
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict):
        return

    reviewed_commit = payload.get("reviewed_commit")
    reviewed_tree_digest = payload.get("reviewed_tree_digest")
    if (
        not isinstance(reviewed_commit, str)
        or _COMMIT_PATTERN.fullmatch(reviewed_commit) is None
        or not isinstance(reviewed_tree_digest, str)
        or _DIGEST_PATTERN.fullmatch(reviewed_tree_digest) is None
    ):
        return

    try:
        committed_digest = _assured_commit_tree_digest(root, reviewed_commit)
    except ValueError as exc:
        findings.append(
            _finding(
                "ASSURANCE-026",
                CANONICAL_ASSURANCE_ARTIFACT,
                f"cannot prove reviewed-commit tree binding: {exc}",
            )
        )
        return
    if committed_digest != reviewed_tree_digest:
        findings.append(
            _finding(
                "ASSURANCE-026",
                CANONICAL_ASSURANCE_ARTIFACT,
                "reviewed_commit assurance-covered tree does not match "
                "reviewed_tree_digest; analytical evidence cannot be rebound to a "
                "different implementation tree",
            )
        )


def _mutation_case_id(raw: object) -> str | None:
    if not isinstance(raw, dict):
        return None
    value = raw.get("id")
    return value if isinstance(value, str) and value.strip() == value and value else None


def _merge_mutation_contracts(
    primary: Mapping[str, Any],
    supplement: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> dict[str, Any]:
    """Return the canonical mutation surface after one explicit governed overlay."""

    path = _MUTATION_SUPPLEMENT_PATH
    missing = _MUTATION_FIELDS - set(supplement)
    unknown = set(supplement) - _MUTATION_FIELDS
    if missing or unknown:
        findings.append(
            _finding(
                "GOV-MUTATION-001",
                path,
                "supplement fields disagree with mutation schema; "
                f"missing={sorted(missing)}, unknown={sorted(unknown)}",
            )
        )
    if supplement.get("schema_version") != _MUTATION_SCHEMA:
        findings.append(
            _finding("GOV-MUTATION-002", path, "unsupported mutation supplement schema")
        )
    contract_id = supplement.get("contract_id")
    if (
        not isinstance(contract_id, str)
        or not contract_id.strip()
        or contract_id != contract_id.strip()
    ):
        findings.append(
            _finding("GOV-MUTATION-003", path, "supplement contract_id must be nonblank")
        )
    for field in ("execution", "timeout_seconds"):
        if supplement.get(field) != primary.get(field):
            findings.append(
                _finding(
                    "GOV-MUTATION-004",
                    path,
                    f"supplement {field} must exactly match the canonical mutation contract",
                )
            )

    primary_cases = primary.get("cases")
    supplement_cases = supplement.get("cases")
    if (
        not isinstance(primary_cases, list)
        or not isinstance(supplement_cases, list)
        or not supplement_cases
    ):
        findings.append(
            _finding(
                "GOV-MUTATION-005",
                path,
                "primary and supplemental mutation cases must be nonempty arrays",
            )
        )
        return dict(primary)

    combined: dict[str, object] = {}
    primary_ids: set[str] = set()
    for raw in primary_cases:
        case_id = _mutation_case_id(raw)
        if case_id is None or case_id in primary_ids:
            findings.append(
                _finding(
                    "GOV-MUTATION-006",
                    "governance/mutation_contract.toml",
                    "primary mutation case IDs must be unique nonblank strings",
                )
            )
            continue
        primary_ids.add(case_id)
        combined[case_id] = raw

    supplement_ids: set[str] = set()
    for raw in supplement_cases:
        case_id = _mutation_case_id(raw)
        if case_id is None or case_id in supplement_ids:
            findings.append(
                _finding(
                    "GOV-MUTATION-006",
                    path,
                    "supplement mutation case IDs must be unique nonblank strings",
                )
            )
            continue
        supplement_ids.add(case_id)
        if case_id in primary_ids and case_id not in _MUTATION_OVERRIDES:
            findings.append(
                _finding(
                    "GOV-MUTATION-007",
                    path,
                    f"unauthorized mutation-case override: {case_id}",
                )
            )
            continue
        combined[case_id] = raw

    missing_overrides = _MUTATION_OVERRIDES - supplement_ids
    if missing_overrides:
        findings.append(
            _finding(
                "GOV-MUTATION-008",
                path,
                f"required scoped mutation override is missing: {sorted(missing_overrides)}",
            )
        )
    merged = dict(primary)
    merged["cases"] = list(combined.values())
    return merged


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
        _ADVERSARIAL_TEST_SCHEMA,
        findings,
    )
    primary_mutation = _read_toml(
        repository_root,
        "governance/mutation_contract.toml",
        _MUTATION_SCHEMA,
        findings,
    )
    assurance_mutation = _read_toml(
        repository_root,
        _MUTATION_SUPPLEMENT_PATH,
        _MUTATION_SCHEMA,
        findings,
    )
    mutation = _merge_mutation_contracts(
        primary_mutation,
        assurance_mutation,
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
    assurance = _read_toml(
        repository_root,
        "governance/assurance_contract.toml",
        _ASSURANCE_CONTRACT_SCHEMA,
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
        "governance/assurance_contract.toml": assurance,
    }
    audit_governance_contract_shapes(repository_root, contracts, findings)
    audit_governance_links(contracts, findings)
    audit_adversarial_contract(
        repository_root,
        tests,
        findings,
        mutation_contract=mutation,
    )

    layer_by_module, graph, mutation_map, metrics = _audit_architecture(
        repository_root,
        tracked,
        architecture,
        network,
        findings,
    )
    audit_architecture_boundaries(
        layer_by_module=layer_by_module,
        graph=graph,
        network_contract=network,
        findings=findings,
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
    _audit_defects_and_review(
        repository_root,
        findings,
        assurance_contract=assurance,
    )
    _audit_assurance_reviewed_tree_binding(repository_root, findings)

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
