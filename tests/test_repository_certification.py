from __future__ import annotations

import subprocess
from pathlib import Path

from constructionsight.repository_certification import audit_repository, main

_MINIMAL_PYPROJECT = """\
[project]
name = "cert-fixture"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
cert-fixture = "constructionsight.fixture_cli:main"

[tool.ruff.lint]
ignore = []

[tool.mypy]
strict = true
warn_unused_ignores = true
warn_return_any = true
warn_unreachable = true

[tool.pytest.ini_options]
testpaths = ["tests"]
"""

_MINIMAL_WORKFLOW = """\
name: CI
on:
  pull_request:
    branches:
      - main
  push:
    branches:
      - main
permissions:
  contents: read
jobs:
  quality:
    strategy:
      matrix:
        python-version:
          - "3.11"
          - "3.12"
    steps:
      - run: git ls-files --stage
      - run: python -m ruff check src tests
      - run: python -m mypy src
      - run: python -m compileall -q src tests
      - run: python -m pytest --strict-config --strict-markers -ra
      - run: python -m pip check
      - run: git diff --check
      - run: python -m constructionsight.repository_certification --root . --require-clean-worktree
      - run: constructionsight audit-adapters
      - run: constructionsight audit-source-coverage data/source_registry.seed.json
"""


def _run(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _write(root: Path, relative_path: str, content: str) -> None:
    destination = root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def _build_repository(root: Path) -> None:
    _run(root, "init")
    _run(root, "config", "user.email", "certification@example.invalid")
    _run(root, "config", "user.name", "Certification Test")
    _write(root, "pyproject.toml", _MINIMAL_PYPROJECT)
    _write(root, ".github/workflows/ci.yml", _MINIMAL_WORKFLOW)
    _write(root, "README.md", "# Fixture\n")
    _write(root, "src/constructionsight/fixture_cli.py", "def main() -> int:\n    return 0\n")
    _write(root, "tests/test_fixture.py", "def test_fixture() -> None:\n    assert True\n")
    _write(root, "data/source_registry.seed.json", "[]\n")
    _run(root, "add", ".")
    _run(root, "commit", "-m", "Create certification fixture")


def test_clean_repository_passes(tmp_path: Path) -> None:
    _build_repository(tmp_path)

    report = audit_repository(tmp_path, require_clean_worktree=True)

    assert report.passed is True
    assert report.finding_count == 0
    assert report.source_python_count == 1
    assert report.test_python_count == 1


def test_suppressions_and_transient_files_fail(tmp_path: Path) -> None:
    _build_repository(tmp_path)
    suppression = "# " + "no" + "qa"
    _write(
        tmp_path,
        "src/constructionsight/bad.py",
        f"value = 1  {suppression}\n",
    )
    _write(tmp_path, "tests/__pycache__/bad.pyc", "tracked cache\n")
    _run(tmp_path, "add", ".")
    _run(tmp_path, "commit", "-m", "Add prohibited files")

    report = audit_repository(tmp_path)

    codes = {finding.code for finding in report.findings}
    assert "CERT-SUPPRESS-001" in codes
    assert "CERT-PATH-002" in codes
    assert "CERT-PATH-003" in codes


def test_broken_local_markdown_link_fails(tmp_path: Path) -> None:
    _build_repository(tmp_path)
    _write(tmp_path, "README.md", "# Fixture\n\n[Missing](docs/missing.md)\n")
    _run(tmp_path, "add", "README.md")
    _run(tmp_path, "commit", "-m", "Add broken link")

    report = audit_repository(tmp_path)

    assert any(finding.code == "CERT-DOC-001" for finding in report.findings)


def test_tracked_symbolic_link_fails_without_reading_target(tmp_path: Path) -> None:
    _build_repository(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("outside\n", encoding="utf-8")
    link = tmp_path / "docs/external.md"
    link.parent.mkdir(parents=True)
    link.symlink_to(outside)
    _run(tmp_path, "add", "docs/external.md")
    _run(tmp_path, "commit", "-m", "Add prohibited symbolic link")

    report = audit_repository(tmp_path)

    assert any(
        finding.code == "CERT-PATH-005"
        and finding.path == "docs/external.md"
        for finding in report.findings
    )


def test_dirty_worktree_fails_when_required(tmp_path: Path) -> None:
    _build_repository(tmp_path)
    _write(tmp_path, "README.md", "# Modified fixture\n")

    report = audit_repository(tmp_path, require_clean_worktree=True)

    assert any(finding.code == "CERT-GIT-001" for finding in report.findings)


def test_missing_console_script_attribute_fails(tmp_path: Path) -> None:
    _build_repository(tmp_path)
    _write(tmp_path, "src/constructionsight/fixture_cli.py", "VALUE = 1\n")
    _run(tmp_path, "add", "src/constructionsight/fixture_cli.py")
    _run(tmp_path, "commit", "-m", "Remove script target")

    report = audit_repository(tmp_path)

    assert any(finding.code == "CERT-SCRIPT-003" for finding in report.findings)


def test_cli_returns_failure_for_findings(tmp_path: Path) -> None:
    _build_repository(tmp_path)
    _write(tmp_path, "README.md", "# Fixture without final newline")
    _run(tmp_path, "add", "README.md")
    _run(tmp_path, "commit", "-m", "Add text defect")

    exit_code = main(["--root", str(tmp_path), "--json-output"])

    assert exit_code == 1
