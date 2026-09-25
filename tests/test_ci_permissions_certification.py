from __future__ import annotations

from pathlib import Path

from constructionsight.ci_permissions_certification import (
    audit_ci_permissions,
    top_level_permissions,
)

_EXACT = """\
name: CI
permissions:
  contents: read
  actions: read
  pull-requests: read
jobs:
  quality:
    runs-on: ubuntu-latest
"""


def _write(root: Path, workflow: str) -> None:
    path = root / ".github/workflows/ci.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow, encoding="utf-8")


def test_exact_read_only_permissions_pass(tmp_path: Path) -> None:
    _write(tmp_path, _EXACT)

    assert top_level_permissions(_EXACT) == {
        "actions": "read",
        "contents": "read",
        "pull-requests": "read",
    }
    assert audit_ci_permissions(tmp_path) == ()


def test_write_permission_fails(tmp_path: Path) -> None:
    _write(tmp_path, _EXACT.replace("actions: read", "actions: write"))

    findings = audit_ci_permissions(tmp_path)

    assert len(findings) == 1
    assert findings[0].code == "CERT-CI-005"


def test_extra_permission_fails(tmp_path: Path) -> None:
    _write(
        tmp_path,
        _EXACT.replace("  pull-requests: read\n", "  issues: read\n  pull-requests: read\n"),
    )

    assert audit_ci_permissions(tmp_path)


def test_scalar_or_duplicate_permissions_fail_closed(tmp_path: Path) -> None:
    _write(tmp_path, _EXACT.replace("permissions:", "permissions: read-all"))

    assert audit_ci_permissions(tmp_path)

    _write(
        tmp_path,
        _EXACT.replace(
            "  pull-requests: read\n",
            "  contents: read\n  pull-requests: read\n",
        ),
    )

    assert audit_ci_permissions(tmp_path)
