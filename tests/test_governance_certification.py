from __future__ import annotations

from pathlib import Path
from typing import Any

from constructionsight.architecture_certification import _audit_architecture
from constructionsight.authority_certification import (
    _audit_authorization,
    _audit_defects_and_review,
    _audit_network,
)
from constructionsight.dependency_certification import audit_dependencies
from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.traceability_certification import _audit_capabilities

_HASH = "a" * 64


def _write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return Path(relative)


def _layer(
    name: str,
    pattern: str,
    *,
    default: bool = False,
    allowed: list[str] | None = None,
    forbidden: list[str] | None = None,
    network: bool = False,
    persistence: bool = False,
    filesystem_write: bool = False,
    subprocess: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "responsibility": f"{name} test layer",
        "path_patterns": [pattern],
        "default": default,
        "allowed_internal_layers": allowed or [name],
        "forbidden_internal_layers": forbidden or [],
        "network": network,
        "persistence": persistence,
        "filesystem_write": filesystem_write,
        "subprocess": subprocess,
        "operator": False,
        "authority_bearing": persistence or filesystem_write,
    }


def _architecture(*layers: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "constructionsight.architecture-contract/v1",
        "prohibit_module_cycles": True,
        "layers": list(layers),
    }


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def _hashed_lock(requirement: str) -> str:
    return f"{requirement} --hash=sha256:{_HASH}\n"


def test_architecture_rejects_forbidden_reverse_dependency(tmp_path: Path) -> None:
    tracked = (
        _write(tmp_path, "src/constructionsight/domain.py", "import constructionsight.transport\n"),
        _write(tmp_path, "src/constructionsight/transport.py", "VALUE = 1\n"),
    )
    contract = _architecture(
        _layer(
            "domain",
            r"src/constructionsight/domain\.py",
            allowed=["domain"],
            forbidden=["transport"],
        ),
        _layer(
            "transport",
            r"src/constructionsight/transport\.py",
            allowed=["transport"],
            network=True,
        ),
        _layer("application", r"a^", default=True),
    )
    findings: list[GovernanceFinding] = []

    _audit_architecture(tmp_path, tracked, contract, {"policies": []}, findings)

    assert "ARCH-IMPORT-001" in _codes(findings)


def test_architecture_rejects_import_cycle(tmp_path: Path) -> None:
    tracked = (
        _write(tmp_path, "src/constructionsight/a.py", "import constructionsight.b\n"),
        _write(tmp_path, "src/constructionsight/b.py", "import constructionsight.a\n"),
    )
    contract = _architecture(_layer("application", r"a^", default=True))
    findings: list[GovernanceFinding] = []

    _, _, _, metrics = _audit_architecture(
        tmp_path,
        tracked,
        contract,
        {"policies": []},
        findings,
    )

    assert metrics.architecture_cycles == 1
    assert "ARCH-CYCLE-001" in _codes(findings)


def test_architecture_rejects_undeclared_network_client(tmp_path: Path) -> None:
    tracked = (
        _write(tmp_path, "src/constructionsight/transport.py", "import httpx\n"),
    )
    contract = _architecture(
        _layer(
            "transport",
            r"src/constructionsight/transport\.py",
            default=True,
            network=True,
        )
    )
    findings: list[GovernanceFinding] = []

    _audit_architecture(tmp_path, tracked, contract, {"policies": []}, findings)

    assert "NET-BOUNDARY-001" in _codes(findings)


def test_architecture_rejects_mutation_in_read_only_layer(tmp_path: Path) -> None:
    tracked = (
        _write(
            tmp_path,
            "src/constructionsight/domain.py",
            "from pathlib import Path\nPath('x').write_text('x')\n",
        ),
    )
    contract = _architecture(
        _layer("domain", r"src/constructionsight/domain\.py", default=True)
    )
    findings: list[GovernanceFinding] = []

    _audit_architecture(tmp_path, tracked, contract, {"policies": []}, findings)

    assert "ARCH-CAP-004" in _codes(findings)


def _capability(
    *,
    capability_id: str,
    status: str,
    owning_layer: str,
    pattern: str,
    default_owner: bool,
) -> dict[str, Any]:
    return {
        "id": capability_id,
        "status": status,
        "business_intent": "test intent",
        "owning_layer": owning_layer,
        "module_patterns": [pattern],
        "default_owner": default_owner,
        "tests": ["tests/evidence.py"],
        "doctrine": ["docs/doctrine.md"],
        "adrs": ["docs/adr.md"],
        "persistence": "none",
        "operator_exposure": "none",
        "network_authority": False,
        "mutation_authority": False,
        "authorization_model": "not-applicable",
        "provenance_rule": "retain evidence",
        "compatibility_rule": "explicit",
        "failure_rule": "fail closed",
        "limitation_rule": "test only",
        "negative_constraints": ["no network"],
        "future_entry_conditions": ["entry review"] if status == "planned" else [],
        "replacement": "",
        "network_policy_ids": [],
        "authorization_operation_ids": [],
    }


def test_capability_registry_rejects_planned_runtime_exposure(tmp_path: Path) -> None:
    tracked = (_write(tmp_path, "src/constructionsight/planned.py", "VALUE = 1\n"),)
    _write(tmp_path, "tests/evidence.py", "def test_evidence():\n    assert True\n")
    _write(tmp_path, "docs/doctrine.md", "# Doctrine\n")
    _write(tmp_path, "docs/adr.md", "# ADR\n")
    contract = {
        "capabilities": [
            _capability(
                capability_id="CS-CAP-001",
                status="planned",
                owning_layer="application",
                pattern=r"src/constructionsight/planned\.py",
                default_owner=True,
            )
        ]
    }
    findings: list[GovernanceFinding] = []

    _audit_capabilities(
        tmp_path,
        tracked,
        contract,
        {"constructionsight.planned": "application"},
        findings,
    )

    assert "CAP-RUNTIME-001" in _codes(findings)


def test_capability_registry_rejects_symlinked_governance_artifact(
    tmp_path: Path,
) -> None:
    tracked = (_write(tmp_path, "src/constructionsight/current.py", "VALUE = 1\n"),)
    _write(tmp_path, "tests/evidence.py", "def test_evidence():\n    assert True\n")
    _write(tmp_path, "docs/adr.md", "# ADR\n")
    outside = tmp_path.parent / f"{tmp_path.name}-doctrine.md"
    outside.write_text("outside doctrine\n", encoding="utf-8")
    doctrine = tmp_path / "docs/doctrine.md"
    doctrine.symlink_to(outside)
    contract = {
        "capabilities": [
            _capability(
                capability_id="CS-CAP-001",
                status="implemented",
                owning_layer="application",
                pattern=r"src/constructionsight/current\.py",
                default_owner=True,
            )
        ]
    }
    findings: list[GovernanceFinding] = []

    _audit_capabilities(
        tmp_path,
        tracked,
        contract,
        {"constructionsight.current": "application"},
        findings,
    )

    assert "CAP-ARTIFACT-001" in _codes(findings)


def _dependency_entry() -> dict[str, Any]:
    return {
        "name": "example",
        "canonical_project": "example",
        "extras": [],
        "version": "1.0.0",
        "classification": "runtime",
        "purpose": "test",
        "capabilities": ["CS-CAP-001"],
        "authoritative_registry": "https://pypi.org/project/example/1.0.0/",
        "authoritative_project_source": "https://example.invalid/project",
        "license": "MIT",
        "security_review": "reviewed",
        "maintenance_review": "reviewed",
        "reviewed_on": "2026-07-15",
        "review_process": "verify identity",
        "replacement_considerations": "stdlib",
    }


def test_dependency_audit_rejects_mutable_action_tag(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\ndependencies = ['example==1.0.0']\n",
    )
    _write(tmp_path, "requirements/test.lock", _hashed_lock("example==1.0.0"))
    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        "steps:\n  - uses: actions/checkout@v4\n",
    )
    findings: list[GovernanceFinding] = []

    audit_dependencies(
        tmp_path,
        {
            "dependencies": [_dependency_entry()],
            "lock_files": ["requirements/test.lock"],
        },
        findings,
    )

    assert "DEP-ACTION-001" in _codes(findings)


def test_dependency_audit_rejects_nonexact_direct_pin(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\ndependencies = ['example>=1.0.0']\n",
    )
    _write(tmp_path, "requirements/test.lock", _hashed_lock("example==1.0.0"))
    findings: list[GovernanceFinding] = []

    audit_dependencies(
        tmp_path,
        {
            "dependencies": [_dependency_entry()],
            "lock_files": ["requirements/test.lock"],
        },
        findings,
    )

    assert "DEP-PIN-001" in _codes(findings)


def _authorization_operation() -> dict[str, Any]:
    return {
        "id": "CS-AUTH-001",
        "module_patterns": [r"src/constructionsight/.*\.py"],
        "action": "mutate",
        "resource": "exact resource",
        "impact": "high",
        "actor_model": "boolean",
        "exact_scope": "exact",
        "current_state": "current",
        "granted_authority": ["one mutation"],
        "denied_authority": ["scope expansion"],
        "issuance": "preflight",
        "validity": "single use",
        "reuse_rule": "none",
        "revocation_rule": "state change",
        "reason_required": True,
        "expected_identity": "required",
        "stale_state_rule": "reject stale",
        "audit_identity": "digest",
        "audit_event": "required",
        "failure_posture": "fail-closed",
        "boolean_confirmation_allowed": True,
    }


def test_authorization_rejects_boolean_only_high_impact_authority() -> None:
    findings: list[GovernanceFinding] = []

    _audit_authorization(
        {"operations": [_authorization_operation()]},
        {},
        findings,
    )

    assert "AUTH-BOOLEAN-001" in _codes(findings)


def test_network_contract_rejects_incomplete_policy() -> None:
    findings: list[GovernanceFinding] = []

    _audit_network(
        {"policies": [{"id": "CS-NET-001", "module": "constructionsight.net"}]},
        findings,
    )

    assert "NET-CONTRACT-003" in _codes(findings)


def test_active_defect_is_a_certification_blocker(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "governance/active_defects.toml",
        "schema_version = 'constructionsight.active-defects/v1'\n"
        "[[defects]]\nid = 'CS-TEST-001'\n",
    )
    _write(
        tmp_path,
        "governance/resolved_defects.toml",
        "schema_version = 'constructionsight.resolved-defects/v1'\ndefects = []\n",
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-ACTIVE-001" in _codes(findings)
