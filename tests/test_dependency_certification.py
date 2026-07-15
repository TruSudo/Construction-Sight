from __future__ import annotations

from pathlib import Path
from typing import Any

from constructionsight.dependency_certification import (
    audit_dependencies,
    audit_dependency_agreement,
)
from constructionsight.governance_certification_core import GovernanceFinding

_HASH = "a" * 64


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _locked(requirement: str) -> str:
    return f"{requirement} --hash=sha256:{_HASH}\n"


def _entry() -> dict[str, Any]:
    return {
        "name": "example",
        "canonical_project": "example",
        "extras": [],
        "version": "2.0",
        "classification": "runtime",
        "purpose": "test",
        "capabilities": ["CS-CAP-001"],
        "authoritative_registry": "https://pypi.org/project/example/2.0/",
        "authoritative_project_source": "https://example.invalid/project",
        "license": "MIT",
        "security_review": "reviewed",
        "maintenance_review": "reviewed",
        "reviewed_on": "2026-07-15",
        "review_process": "verify identity",
        "replacement_considerations": "stdlib",
    }


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_registry_version_must_equal_direct_declaration(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\ndependencies = ['example==2.0']\n",
    )
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
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\ndependencies = ['example==2.0']\n",
    )
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
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\n"
        "dependencies = ['example[b,a]==2.0']\n",
    )
    _write(tmp_path, "requirements/test.lock", _locked("Example[a,b]==2.0"))
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
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\ndependencies = ['example==2.0']\n",
    )
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


def test_canonical_dependency_audit_rejects_mutable_action_tag(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\ndependencies = ['example==2.0']\n",
    )
    _write(tmp_path, "requirements/test.lock", _locked("example==2.0"))
    _write(
        tmp_path,
        ".github/workflows/ci.yml",
        "steps:\n  - uses: actions/checkout@v4\n",
    )
    findings: list[GovernanceFinding] = []

    audit_dependencies(
        tmp_path,
        {
            "dependencies": [_entry()],
            "lock_files": ["requirements/test.lock"],
        },
        findings,
    )

    assert "DEP-ACTION-001" in _codes(findings)


def test_canonical_dependency_audit_rejects_nonexact_direct_pin(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "pyproject.toml",
        "[build-system]\nrequires = []\nbuild-backend = 'x'\n"
        "[project]\nname = 'x'\nversion = '1'\ndependencies = ['example>=2.0']\n",
    )
    _write(tmp_path, "requirements/test.lock", _locked("example==2.0"))
    findings: list[GovernanceFinding] = []

    audit_dependencies(
        tmp_path,
        {
            "dependencies": [_entry()],
            "lock_files": ["requirements/test.lock"],
        },
        findings,
    )

    assert "DEP-PIN-001" in _codes(findings)
