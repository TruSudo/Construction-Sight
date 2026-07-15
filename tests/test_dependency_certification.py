from __future__ import annotations

from pathlib import Path

from constructionsight.dependency_certification import audit_dependency_agreement
from constructionsight.governance_certification_core import GovernanceFinding


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
    _write(tmp_path, "requirements/test.lock", "example==1.0\n")
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
    _write(tmp_path, "requirements/test.lock", "Example[a,b]==2.0\n")
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
