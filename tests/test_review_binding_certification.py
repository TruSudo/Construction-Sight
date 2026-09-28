from __future__ import annotations

from pathlib import Path

import pytest

from constructionsight.authority_certification import (
    _audit_defects_and_review,
    _reviewed_tree_digest,
)
from constructionsight.governance_certification_core import (
    GovernanceContractError,
    GovernanceFinding,
)
from tests.support.assurance import (
    active_ledger,
    git,
    initialize_repository,
    resolved_ledger,
    rewrite_assurance,
    write,
    write_assurance,
)


def _codes(
    findings: list[GovernanceFinding],
    *prefixes: str,
) -> set[str]:
    return {
        finding.code
        for finding in findings
        if any(finding.code.startswith(prefix) for prefix in prefixes)
    }


def _prepare_complete_closure(
    root: Path,
) -> tuple[str, str, dict[str, str], dict[str, object], dict[str, object]]:
    initialize_repository(root)
    discovery_commit = git(root, "rev-parse", "HEAD")
    original = {
        "id": "CS-SR-001",
        "severity": "P0",
        "area": "closure-integrity",
        "root_cause": "Assured facts could change during finalization.",
        "discovered_against": discovery_commit,
        "required_resolution": "Preserve exact facts and prove resolution ancestry.",
    }
    write(root, "governance/active_defects.toml", active_ledger([original]))
    write(root, "docs/evidence.md", "reviewed correction evidence\n")
    write(
        root,
        "tests/test_resolution.py",
        "def test_resolution() -> None:\n    assert True\n",
    )
    write(root, "src/constructionsight/reviewed.py", "VALUE = 'corrected'\n")
    write(
        root,
        "docs/assurance/defect_closures/CS-SR-001.md",
        "# CS-SR-001 closure\n\nCorrection and regression evidence retained.\n",
    )
    git(root, "add", ".")
    git(root, "commit", "-m", "implement assured correction")
    reviewed_commit = git(root, "rev-parse", "HEAD")
    resolution_tree = git(root, "rev-parse", f"{reviewed_commit}^{{tree}}")
    reviewed_tree_digest = _reviewed_tree_digest(root)
    report = write_assurance(
        root,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
    )
    closure: dict[str, object] = {
        **original,
        "resolution_summary": "Implemented and regression-tested the correction.",
        "resolution_commit": reviewed_commit,
        "resolution_tree": resolution_tree,
        "last_active_commit": reviewed_commit,
        "evidence_paths": ["docs/evidence.md"],
        "regression_tests": ["tests/test_resolution.py"],
        "closure_evidence": "docs/assurance/defect_closures/CS-SR-001.md",
    }
    write(root, "governance/active_defects.toml", active_ledger([]))
    write(root, "governance/resolved_defects.toml", resolved_ledger([closure]))
    return reviewed_commit, reviewed_tree_digest, original, closure, report

def test_assurance_binding_survives_synthetic_merge_topology(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    git(tmp_path, "switch", "-c", "feature")
    write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'reviewed'\n")
    git(tmp_path, "add", "src/constructionsight/reviewed.py")
    git(tmp_path, "commit", "-m", "assured implementation")

    reviewed_commit = git(tmp_path, "rev-parse", "HEAD")
    reviewed_tree_digest = _reviewed_tree_digest(tmp_path)
    write_assurance(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
    )
    write(
        tmp_path,
        "governance/active_defects.toml",
        'schema_version = "constructionsight.active-defects/v1"\n'
        "certification_requires_zero = true\n"
        "# permitted post-assurance finalization change\n"
        "defects = []\n",
    )
    git(tmp_path, "add", "governance")
    git(tmp_path, "commit", "-m", "finalize assurance")

    git(tmp_path, "switch", "main")
    git(tmp_path, "merge", "--no-ff", "feature", "-m", "synthetic merge ref")
    assert git(tmp_path, "rev-parse", "HEAD^") != reviewed_commit

    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(tmp_path, findings)

    assert _codes(findings, "ASSURANCE-", "DEFECT-REVIEW-", "DEFECT-CLOSURE-") == set()


def test_assurance_binding_rejects_nonpermitted_committed_tree_change(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    reviewed_commit = git(tmp_path, "rev-parse", "HEAD")
    reviewed_tree_digest = _reviewed_tree_digest(tmp_path)
    write_assurance(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
    )
    git(tmp_path, "add", "governance/reviews")
    git(tmp_path, "commit", "-m", "record assurance")

    write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'tampered'\n")
    git(tmp_path, "add", "src/constructionsight/reviewed.py")
    git(tmp_path, "commit", "-m", "tamper assured implementation")

    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(tmp_path, findings)

    assert "ASSURANCE-021" in _codes(findings, "ASSURANCE-")


@pytest.mark.parametrize("state", ["unstaged", "staged", "untracked"])
def test_assured_tree_digest_rejects_dirty_nonpermitted_change(
    tmp_path: Path,
    state: str,
) -> None:
    initialize_repository(tmp_path)
    relative = "src/constructionsight/reviewed.py"
    if state == "untracked":
        relative = "src/constructionsight/untracked.py"
    write(tmp_path, relative, f"VALUE = {state!r}\n")
    if state == "staged":
        git(tmp_path, "add", relative)

    with pytest.raises(GovernanceContractError, match="assurance-covered worktree is dirty"):
        _reviewed_tree_digest(tmp_path)


def test_assured_tree_digest_allows_permitted_finalization_paths(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    baseline = _reviewed_tree_digest(tmp_path)
    write(
        tmp_path,
        "docs/audits/silent_risk_certification_2026-07-15.md",
        "permitted finalization evidence\n",
    )
    write(tmp_path, "governance/reviews/evidence/uncommitted.json", "{}\n")

    assert _reviewed_tree_digest(tmp_path) == baseline


def test_assurance_artifact_rejects_unknown_fields(tmp_path: Path) -> None:
    initialize_repository(tmp_path)
    reviewed_commit = git(tmp_path, "rev-parse", "HEAD")
    report = write_assurance(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=_reviewed_tree_digest(tmp_path),
    )
    report["unexpected_authority"] = True
    rewrite_assurance(tmp_path, report)
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "ASSURANCE-003" in _codes(findings, "ASSURANCE-")


def test_complete_closure_binds_assured_facts_and_resolution_history(
    tmp_path: Path,
) -> None:
    _prepare_complete_closure(tmp_path)
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert _codes(findings, "ASSURANCE-", "DEFECT-REVIEW-", "DEFECT-CLOSURE-") == set()


def test_closure_rejects_changed_reviewed_defect_facts(tmp_path: Path) -> None:
    _reviewed_commit, _digest, _original, closure, _report = _prepare_complete_closure(
        tmp_path
    )
    mutated = dict(closure)
    mutated["root_cause"] = "Rewritten after assurance."
    write(tmp_path, "governance/resolved_defects.toml", resolved_ledger([mutated]))
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-CLOSURE-009" in _codes(findings, "DEFECT-CLOSURE-")


def test_incremental_closure_allows_other_defects_to_remain_active(
    tmp_path: Path,
) -> None:
    initialize_repository(tmp_path)
    discovery_commit = git(tmp_path, "rev-parse", "HEAD")
    first = {
        "id": "CS-SR-001",
        "severity": "P0",
        "area": "closure-integrity",
        "root_cause": "First root cause.",
        "discovered_against": discovery_commit,
        "required_resolution": "Correct first root cause.",
    }
    second = {
        "id": "CS-SR-002",
        "severity": "P1",
        "area": "remaining-work",
        "root_cause": "Second root cause remains active.",
        "discovered_against": discovery_commit,
        "required_resolution": "Correct second root cause later.",
    }
    write(tmp_path, "governance/active_defects.toml", active_ledger([first, second]))
    write(tmp_path, "docs/evidence.md", "first correction evidence\n")
    write(
        tmp_path,
        "tests/test_resolution.py",
        "def test_resolution() -> None:\n    assert True\n",
    )
    write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'corrected'\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "correct first defect")
    resolution_commit = git(tmp_path, "rev-parse", "HEAD")
    resolution_tree = git(tmp_path, "rev-parse", f"{resolution_commit}^{{tree}}")
    write(
        tmp_path,
        "docs/assurance/defect_closures/CS-SR-001.md",
        "# CS-SR-001 closure\n",
    )
    closure = {
        **first,
        "resolution_summary": "Corrected first defect with regression coverage.",
        "resolution_commit": resolution_commit,
        "resolution_tree": resolution_tree,
        "last_active_commit": resolution_commit,
        "evidence_paths": ["docs/evidence.md"],
        "regression_tests": ["tests/test_resolution.py"],
        "closure_evidence": "docs/assurance/defect_closures/CS-SR-001.md",
    }
    write(tmp_path, "governance/active_defects.toml", active_ledger([second]))
    write(tmp_path, "governance/resolved_defects.toml", resolved_ledger([closure]))
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert _codes(findings, "DEFECT-CLOSURE-") == set()
    assert "DEFECT-ACTIVE-001" in _codes(findings, "DEFECT-ACTIVE-")
    assert "ASSURANCE-001" in _codes(findings, "ASSURANCE-")


def test_closure_rejects_missing_resolution_commit(tmp_path: Path) -> None:
    _reviewed_commit, _digest, _original, closure, _report = _prepare_complete_closure(
        tmp_path
    )
    mutated = dict(closure)
    mutated["resolution_commit"] = "f" * 40
    write(tmp_path, "governance/resolved_defects.toml", resolved_ledger([mutated]))
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-CLOSURE-004" in _codes(findings, "DEFECT-CLOSURE-")


def test_closure_rejects_resolution_outside_reviewed_history(tmp_path: Path) -> None:
    reviewed_commit, _digest, _original, closure, _report = _prepare_complete_closure(
        tmp_path
    )
    tree = git(tmp_path, "rev-parse", f"{reviewed_commit}^{{tree}}")
    unrelated_commit = git(tmp_path, "commit-tree", tree, "-m", "unrelated resolution")
    mutated = dict(closure)
    mutated["resolution_commit"] = unrelated_commit
    write(tmp_path, "governance/resolved_defects.toml", resolved_ledger([mutated]))
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-CLOSURE-006" in _codes(findings, "DEFECT-CLOSURE-")


def test_assurance_artifact_must_bind_complete_active_facts(tmp_path: Path) -> None:
    _reviewed_commit, _digest, _original, _closure, report = _prepare_complete_closure(
        tmp_path
    )
    report["reviewed_active_defects_digest"] = "0" * 64
    rewrite_assurance(tmp_path, report)
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-REVIEW-004" in _codes(findings, "DEFECT-REVIEW-")


def test_assurance_requires_reviewed_active_defect_digest(tmp_path: Path) -> None:
    _reviewed_commit, _digest, _original, _closure, report = _prepare_complete_closure(
        tmp_path
    )
    del report["reviewed_active_defects_digest"]
    rewrite_assurance(tmp_path, report)
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert {"ASSURANCE-003", "ASSURANCE-019"} <= _codes(findings, "ASSURANCE-")


def test_assurance_rejects_nonexistent_reviewed_commit(tmp_path: Path) -> None:
    _reviewed_commit, _digest, _original, _closure, report = _prepare_complete_closure(
        tmp_path
    )
    report["reviewed_commit"] = "f" * 40
    report["reviewed_active_defects_digest"] = "0" * 64
    rewrite_assurance(tmp_path, report)
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "ASSURANCE-017" in _codes(findings, "ASSURANCE-")


def test_assurance_rejects_reviewed_commit_outside_current_history(
    tmp_path: Path,
) -> None:
    reviewed_commit, _digest, _original, _closure, report = _prepare_complete_closure(
        tmp_path
    )
    reviewed_tree = git(tmp_path, "rev-parse", f"{reviewed_commit}^{{tree}}")
    unrelated_reviewed_commit = git(
        tmp_path,
        "commit-tree",
        reviewed_tree,
        "-m",
        "unrelated assured implementation",
    )
    report["reviewed_commit"] = unrelated_reviewed_commit
    rewrite_assurance(tmp_path, report)
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "ASSURANCE-017" in _codes(findings, "ASSURANCE-")
