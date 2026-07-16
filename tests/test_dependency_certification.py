from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from constructionsight.dependency_certification import (
    audit_dependencies,
    audit_dependency_agreement,
)
from constructionsight.governance_certification_core import GovernanceFinding

_HASH = "a" * 64
_REQUIRED_CI = """name: CI
steps:
  - uses: actions/checkout@1111111111111111111111111111111111111111 # v1
  - run: python -m pip install --require-hashes --only-binary=:all: --no-deps -r lock
  - run: python -m constructionsight.supply_chain verify-lock
  - run: python -m pip check
  - uses: pypa/gh-action-pip-audit@2222222222222222222222222222222222222222 # reviewed
  - run: python -m constructionsight.supply_chain sbom
  - run: python -m constructionsight.mutation_certification
  - run: python -m constructionsight.repository_certification_v2
"""


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _locked(requirement: str, *, digest: str = _HASH) -> str:
    return f"{requirement} --hash=sha256:{digest}\n"


def _entry() -> dict[str, Any]:
    return {
        "name": "example",
        "canonical_project": "example",
        "extras": [],
        "version": "2.0",
        "classification": "runtime",
        "purpose": "test purpose",
        "capabilities": ["CS-CAP-001"],
        "authoritative_registry": "https://pypi.org/project/example/2.0/",
        "authoritative_project_source": "https://example.invalid/project",
        "license": "MIT",
        "security_review": "reviewed identity and advisories",
        "maintenance_review": "reviewed maintenance",
        "reviewed_on": "2026-07-15",
        "review_process": "verify identity",
        "replacement_considerations": "stdlib replacement review",
    }


def _contract(*, lock_files: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "constructionsight.dependency-contract/v1",
        "contract_id": "test-dependencies",
        "supported_python": ["3.11", "3.12"],
        "supported_runner": "github-hosted-ubuntu-x86_64",
        "lock_files": lock_files or ["requirements/test.lock"],
        "lock_format": "pip-requirements-sha256-v1",
        "require_hashes": True,
        "binary_only": True,
        "reject_unexpected_installed_distributions": True,
        "expected_project_distribution": "constructionsight==0.1.0",
        "bootstrap_distributions": [
            "pip==26.1.2",
            "setuptools==83.0.0",
            "wheel==0.47.0",
        ],
        "install_policy": "exact hashed install",
        "hash_policy": "every row is hashed",
        "vulnerability_tool": "pinned audit action",
        "vulnerability_failure_policy": "all findings are fatal",
        "vulnerability_exceptions": "governance/vulnerability_exceptions.toml",
        "sbom_format": "CycloneDX 1.5 JSON",
        "sbom_output": "reports/sbom.json",
        "review_evidence": "docs/adr.md",
        "dependencies": [_entry()],
    }


def _lock(example_version: str = "2.0") -> str:
    return (
        _locked(f"example=={example_version}")
        + _locked("pip==26.1.2")
        + _locked("setuptools==83.0.0")
        + _locked("wheel==0.47.0")
    )


def _project(root: Path, dependency: str = "example==2.0") -> None:
    _write(
        root,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        f"[project]\nname = 'x'\nversion = '1'\ndependencies = ['{dependency}']\n",
    )
    _write(root, "governance/vulnerability_exceptions.toml", "exceptions = []\n")
    _write(root, "docs/adr.md", "# ADR\n")
    _write(root, ".github/workflows/ci.yml", _REQUIRED_CI)


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_registry_version_must_equal_direct_declaration(tmp_path: Path) -> None:
    _project(tmp_path)
    findings: list[GovernanceFinding] = []

    audit_dependency_agreement(
        tmp_path,
        {
            "dependencies": [
                {"name": "example", "extras": [], "version": "1.0"}
            ],
            "lock_files": [],
        },
        findings,
    )

    assert "DEP-REGISTRY-002" in _codes(findings)


def test_lock_version_must_equal_direct_declaration(tmp_path: Path) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", _locked("example==1.0"))
    findings: list[GovernanceFinding] = []

    audit_dependency_agreement(
        tmp_path,
        {
            "dependencies": [
                {"name": "example", "extras": [], "version": "2.0"}
            ],
            "lock_files": ["requirements/test.lock"],
        },
        findings,
    )

    assert "DEP-LOCK-006" in _codes(findings)


def test_lock_extras_are_canonicalized_and_compared(tmp_path: Path) -> None:
    _project(tmp_path, "example[b,a]==2.0")
    _write(tmp_path, "requirements/test.lock", _locked("example[a,b]==2.0"))
    findings: list[GovernanceFinding] = []

    audit_dependency_agreement(
        tmp_path,
        {
            "dependencies": [
                {"name": "example", "extras": ["a", "b"], "version": "2.0"}
            ],
            "lock_files": ["requirements/test.lock"],
        },
        findings,
    )

    assert findings == []


def test_unhashed_lock_is_a_certification_finding(tmp_path: Path) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", "example==2.0\n")
    findings: list[GovernanceFinding] = []

    audit_dependency_agreement(
        tmp_path,
        {
            "dependencies": [
                {"name": "example", "extras": [], "version": "2.0"}
            ],
            "lock_files": ["requirements/test.lock"],
        },
        findings,
    )

    assert "DEP-LOCK-007" in _codes(findings)


def test_canonical_dependency_audit_accepts_complete_policy(tmp_path: Path) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", _lock())
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, _contract(), findings)

    assert findings == []


def test_canonical_dependency_audit_rejects_mutable_action_tag(tmp_path: Path) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", _lock())
    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        _REQUIRED_CI + "  - uses: actions/setup-python@v6\n",
    )
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, _contract(), findings)

    assert "DEP-ACTION-001" in _codes(findings)


def test_canonical_dependency_audit_rejects_nonexact_direct_pin(
    tmp_path: Path,
) -> None:
    _project(tmp_path, "example>=2.0")
    _write(tmp_path, "requirements/test.lock", _lock())
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, _contract(), findings)

    assert "DEP-PIN-001" in _codes(findings)


def test_canonical_dependency_audit_rejects_duplicate_registry_identity(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", _lock())
    contract = _contract()
    contract["dependencies"] = [_entry(), deepcopy(_entry())]
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, contract, findings)

    assert "DEP-REGISTRY-003" in _codes(findings)


def test_canonical_dependency_audit_rejects_non_table_registry_entry(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", _lock())
    contract = _contract()
    contract["dependencies"] = [_entry(), "not-a-table"]
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, contract, findings)

    assert "DEP-CONTRACT-009" in _codes(findings)


def test_canonical_dependency_audit_rejects_unknown_top_level_field(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", _lock())
    contract = _contract()
    contract["unreviewed_toggle"] = True
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, contract, findings)

    assert "DEP-CONTRACT-000" in _codes(findings)


def test_canonical_dependency_audit_rejects_unsafe_lock_path(tmp_path: Path) -> None:
    _project(tmp_path)
    contract = _contract(lock_files=["../outside.lock"])
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, contract, findings)

    assert "DEP-LOCK-008" in _codes(findings)


def test_canonical_dependency_audit_rejects_bootstrap_disagreement(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    _write(
        tmp_path,
        "requirements/test.lock",
        _locked("example==2.0")
        + _locked("pip==26.1.2")
        + _locked("setuptools==82.0.0")
        + _locked("wheel==0.47.0"),
    )
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, _contract(), findings)

    assert "DEP-LOCK-009" in _codes(findings)


def test_canonical_dependency_audit_rejects_cross_lock_version_drift(
    tmp_path: Path,
) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/py311.lock", _lock("2.0"))
    _write(tmp_path, "requirements/py312.lock", _lock("3.0"))
    findings: list[GovernanceFinding] = []

    audit_dependencies(
        tmp_path,
        _contract(lock_files=["requirements/py311.lock", "requirements/py312.lock"]),
        findings,
    )

    assert "DEP-LOCK-010" in _codes(findings)


def test_canonical_dependency_audit_rejects_missing_ci_gate(tmp_path: Path) -> None:
    _project(tmp_path)
    _write(tmp_path, "requirements/test.lock", _lock())
    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        _REQUIRED_CI.replace(
            "  - run: python -m constructionsight.mutation_certification\n",
            "",
        ),
    )
    findings: list[GovernanceFinding] = []

    audit_dependencies(tmp_path, _contract(), findings)

    assert "DEP-CI-001" in _codes(findings)
