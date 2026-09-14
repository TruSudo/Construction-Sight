from __future__ import annotations

from pathlib import Path

from constructionsight.ci_action_certification import audit_ci_actions

_CHECKOUT = (
    "    uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
    " # v7.0.1; reviewed 2026-09-14; runtime=node24"
)
_SETUP = (
    "    uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97"
    " # v7.0.0; reviewed 2026-09-14; runtime=node24"
)
_AUDIT = (
    "    uses: pypa/gh-action-pip-audit@"
    "fb241f581674a1bb995061d62504857a9ea4b69e"
    " # immutable-reviewed-commit; reviewed 2026-07-15; runtime=composite"
)
_UPLOAD = (
    "    uses: actions/upload-artifact@"
    "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    " # v7.0.1; reviewed 2026-09-14; runtime=node24"
)
_EXACT = "\n".join(
    (
        "name: CI",
        "steps:",
        "  - name: checkout one",
        _CHECKOUT,
        "  - name: checkout two",
        _CHECKOUT,
        "  - name: setup one",
        _SETUP,
        "  - name: setup two",
        _SETUP,
        "  - name: audit",
        _AUDIT,
        "  - name: upload one",
        _UPLOAD,
        "  - name: upload two",
        _UPLOAD,
        "",
    )
)


def _write(root: Path, workflow: str) -> None:
    path = root / ".github/workflows/ci.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow, encoding="utf-8")


def test_exact_reviewed_action_inventory_passes(tmp_path: Path) -> None:
    _write(tmp_path, _EXACT)

    assert audit_ci_actions(tmp_path) == ()


def test_stale_action_commit_fails(tmp_path: Path) -> None:
    stale = _EXACT.replace(
        "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "11bd71901bbe5b1630ceea73d27597364c9af683",
        1,
    )
    _write(tmp_path, stale)

    findings = audit_ci_actions(tmp_path)

    assert any("reviewed commit" in finding.message for finding in findings)


def test_runtime_review_annotation_drift_fails(tmp_path: Path) -> None:
    _write(tmp_path, _EXACT.replace("runtime=node24", "runtime=node20", 1))

    findings = audit_ci_actions(tmp_path)

    assert any("review annotation" in finding.message for finding in findings)


def test_unreviewed_action_repository_fails(tmp_path: Path) -> None:
    unreviewed = _EXACT.replace(
        "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1",
        "example/unreviewed@3d3c42e5aac5ba805825da76410c181273ba90b1",
        1,
    )
    _write(tmp_path, unreviewed)

    findings = audit_ci_actions(tmp_path)

    assert any("unreviewed GitHub Action" in finding.message for finding in findings)


def test_missing_or_unpinned_action_use_fails(tmp_path: Path) -> None:
    missing = _EXACT.replace(_UPLOAD + "\n", "", 1)
    _write(tmp_path, missing)

    findings = audit_ci_actions(tmp_path)

    assert any("must occur exactly" in finding.message for finding in findings)

    unpinned = _EXACT.replace(_SETUP, "    uses: actions/setup-python@v7", 1)
    _write(tmp_path, unpinned)

    findings = audit_ci_actions(tmp_path)

    assert any("exact 40-hex commit" in finding.message for finding in findings)
