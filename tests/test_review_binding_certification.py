from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from constructionsight.authority_certification import (
    _audit_defects_and_review,
    _reviewed_tree_digest,
)
from constructionsight.defect_closure_certification import (
    reviewed_active_defects_digest,
)
from constructionsight.governance_certification_core import (
    GovernanceContractError,
    GovernanceFinding,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _initialize_repository(root: Path) -> None:
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "ConstructionSight Review Test")
    _git(root, "config", "user.email", "review-test@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _write(
        root,
        "governance/active_defects.toml",
        'schema_version = "constructionsight.active-defects/v1"\n'
        "certification_requires_zero = true\n"
        "defects = []\n",
    )
    _write(
        root,
        "governance/resolved_defects.toml",
        'schema_version = "constructionsight.resolved-defects/v1"\ndefects = []\n',
    )
    _write(root, "src/constructionsight/reviewed.py", "VALUE = 'base'\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")


def _write_review(
    root: Path,
    *,
    reviewed_commit: str,
    reviewed_tree_digest: str,
    extra: dict[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {
        "schema_version": "constructionsight.independent-review/v1",
        "status": "passed",
        "reviewer": "independent-test-reviewer",
        "review_method": "adversarial review of the exact reviewed tree",
        "reviewed_commit": reviewed_commit,
        "reviewed_active_defects_digest": reviewed_active_defects_digest(
            root,
            reviewed_commit,
        ),
        "reviewed_tree_digest": reviewed_tree_digest,
        "findings": [],
    }
    if extra:
        payload.update(extra)
    _write(
        root,
        "governance/reviews/independent_review.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )


def _review_codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings if finding.code.startswith("REVIEW-")}


def _closure_codes(findings: list[GovernanceFinding]) -> set[str]:
    return {
        finding.code
        for finding in findings
        if finding.code.startswith(("DEFECT-CLOSURE-", "DEFECT-REVIEW-"))
    }


def _active_ledger(defects: list[dict[str, str]]) -> str:
    lines = [
        'schema_version = "constructionsight.active-defects/v1"',
        "certification_requires_zero = true",
    ]
    if not defects:
        lines.append("defects = []")
    for defect in defects:
        lines.extend(
            [
                "",
                "[[defects]]",
                *(f"{field} = {json.dumps(value)}" for field, value in defect.items()),
            ]
        )
    return "\n".join(lines) + "\n"


def _resolved_ledger(defects: list[dict[str, object]]) -> str:
    lines = ['schema_version = "constructionsight.resolved-defects/v1"']
    if not defects:
        lines.append("defects = []")
    for defect in defects:
        lines.extend(["", "[[defects]]"])
        for field, value in defect.items():
            lines.append(f"{field} = {json.dumps(value)}")
    return "\n".join(lines) + "\n"


def _prepare_complete_closure(
    root: Path,
) -> tuple[str, str, dict[str, str], dict[str, object]]:
    _initialize_repository(root)
    discovery_commit = _git(root, "rev-parse", "HEAD")
    original = {
        "id": "CS-SR-001",
        "severity": "P0",
        "area": "closure-integrity",
        "root_cause": "Reviewed facts could change during finalization.",
        "discovered_against": discovery_commit,
        "required_resolution": "Preserve exact facts and prove resolution ancestry.",
    }
    _write(root, "governance/active_defects.toml", _active_ledger([original]))
    _write(root, "docs/evidence.md", "reviewed correction evidence\n")
    _write(
        root,
        "tests/test_resolution.py",
        "def test_resolution() -> None:\n    assert True\n",
    )
    _write(root, "src/constructionsight/reviewed.py", "VALUE = 'corrected'\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "implement reviewed correction")
    reviewed_commit = _git(root, "rev-parse", "HEAD")
    reviewed_tree_digest = _reviewed_tree_digest(root)
    _write_review(
        root,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
    )
    closure: dict[str, object] = {
        **original,
        "resolution_summary": "Implemented and regression-tested the correction.",
        "resolution_commit": reviewed_commit,
        "evidence_paths": ["docs/evidence.md"],
        "regression_tests": ["tests/test_resolution.py"],
        "review_artifact": "governance/reviews/independent_review.json",
        "reviewed_tree_digest": reviewed_tree_digest,
    }
    _write(root, "governance/active_defects.toml", _active_ledger([]))
    _write(root, "governance/resolved_defects.toml", _resolved_ledger([closure]))
    return reviewed_commit, reviewed_tree_digest, original, closure


def test_review_binding_survives_synthetic_merge_topology(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    _git(tmp_path, "switch", "-c", "feature")
    _write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'reviewed'\n")
    _git(tmp_path, "add", "src/constructionsight/reviewed.py")
    _git(tmp_path, "commit", "-m", "reviewed implementation")

    reviewed_commit = _git(tmp_path, "rev-parse", "HEAD")
    reviewed_tree_digest = _reviewed_tree_digest(tmp_path)
    _write_review(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
    )
    _write(
        tmp_path,
        "governance/active_defects.toml",
        'schema_version = "constructionsight.active-defects/v1"\n'
        "certification_requires_zero = true\n"
        "# permitted post-review finalization change\n"
        "defects = []\n",
    )
    _git(tmp_path, "add", "governance")
    _git(tmp_path, "commit", "-m", "finalize independent review")

    _git(tmp_path, "switch", "main")
    _git(tmp_path, "merge", "--no-ff", "feature", "-m", "synthetic merge ref")
    assert _git(tmp_path, "rev-parse", "HEAD^") != reviewed_commit

    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(tmp_path, findings)

    assert _review_codes(findings) == set()


def test_review_binding_rejects_nonpermitted_committed_tree_change(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    reviewed_commit = _git(tmp_path, "rev-parse", "HEAD")
    reviewed_tree_digest = _reviewed_tree_digest(tmp_path)
    _write_review(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
    )
    _git(tmp_path, "add", "governance/reviews/independent_review.json")
    _git(tmp_path, "commit", "-m", "record review")

    _write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'tampered'\n")
    _git(tmp_path, "add", "src/constructionsight/reviewed.py")
    _git(tmp_path, "commit", "-m", "tamper reviewed implementation")

    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(tmp_path, findings)

    assert "REVIEW-009" in _review_codes(findings)


def test_reviewed_tree_digest_rejects_unstaged_nonpermitted_change(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    _write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'unstaged'\n")

    with pytest.raises(GovernanceContractError, match="review-covered worktree is dirty"):
        _reviewed_tree_digest(tmp_path)


def test_reviewed_tree_digest_rejects_staged_nonpermitted_change(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    _write(tmp_path, "src/constructionsight/reviewed.py", "VALUE = 'staged'\n")
    _git(tmp_path, "add", "src/constructionsight/reviewed.py")

    with pytest.raises(GovernanceContractError, match="review-covered worktree is dirty"):
        _reviewed_tree_digest(tmp_path)


def test_reviewed_tree_digest_rejects_untracked_nonpermitted_change(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    _write(tmp_path, "src/constructionsight/untracked.py", "VALUE = 'untracked'\n")

    with pytest.raises(GovernanceContractError, match="review-covered worktree is dirty"):
        _reviewed_tree_digest(tmp_path)


def test_reviewed_tree_digest_allows_dirty_permitted_finalization_path(
    tmp_path: Path,
) -> None:
    _initialize_repository(tmp_path)
    baseline = _reviewed_tree_digest(tmp_path)
    _write(
        tmp_path,
        "docs/audits/silent_risk_certification_2026-07-15.md",
        "permitted finalization evidence\n",
    )

    assert _reviewed_tree_digest(tmp_path) == baseline


def test_review_binding_rejects_unknown_review_fields(tmp_path: Path) -> None:
    _initialize_repository(tmp_path)
    reviewed_commit = _git(tmp_path, "rev-parse", "HEAD")
    reviewed_tree_digest = _reviewed_tree_digest(tmp_path)
    _write_review(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
        extra={"unexpected_authority": True},
    )
    _git(tmp_path, "add", "governance/reviews/independent_review.json")

    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(tmp_path, findings)

    assert "REVIEW-010" in _review_codes(findings)


def test_complete_closure_binds_reviewed_facts_and_resolution_history(
    tmp_path: Path,
) -> None:
    _prepare_complete_closure(tmp_path)
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert _review_codes(findings) == set()
    assert _closure_codes(findings) == set()


def test_closure_rejects_changed_reviewed_defect_facts(tmp_path: Path) -> None:
    _reviewed_commit, _digest, _original, closure = _prepare_complete_closure(tmp_path)
    mutated = dict(closure)
    mutated["root_cause"] = "Rewritten after review."
    _write(
        tmp_path,
        "governance/resolved_defects.toml",
        _resolved_ledger([mutated]),
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-CLOSURE-003" in _closure_codes(findings)


def test_closure_requires_complete_reviewed_id_accounting(tmp_path: Path) -> None:
    _prepare_complete_closure(tmp_path)
    _write(
        tmp_path,
        "governance/resolved_defects.toml",
        _resolved_ledger([]),
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-CLOSURE-002" in _closure_codes(findings)


def test_closure_rejects_missing_resolution_commit(tmp_path: Path) -> None:
    _reviewed_commit, _digest, _original, closure = _prepare_complete_closure(tmp_path)
    mutated = dict(closure)
    mutated["resolution_commit"] = "f" * 40
    _write(
        tmp_path,
        "governance/resolved_defects.toml",
        _resolved_ledger([mutated]),
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-CLOSURE-005" in _closure_codes(findings)


def test_closure_rejects_resolution_outside_reviewed_history(tmp_path: Path) -> None:
    reviewed_commit, _digest, _original, closure = _prepare_complete_closure(tmp_path)
    tree = _git(tmp_path, "rev-parse", f"{reviewed_commit}^{{tree}}")
    unrelated_commit = _git(tmp_path, "commit-tree", tree, "-m", "unrelated resolution")
    mutated = dict(closure)
    mutated["resolution_commit"] = unrelated_commit
    _write(
        tmp_path,
        "governance/resolved_defects.toml",
        _resolved_ledger([mutated]),
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-CLOSURE-006" in _closure_codes(findings)


def test_review_artifact_must_bind_complete_reviewed_active_facts(
    tmp_path: Path,
) -> None:
    reviewed_commit, reviewed_tree_digest, _original, _closure = _prepare_complete_closure(tmp_path)
    _write_review(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
        extra={"reviewed_active_defects_digest": "0" * 64},
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-REVIEW-004" in _closure_codes(findings)


def test_review_artifact_requires_reviewed_active_defect_digest(
    tmp_path: Path,
) -> None:
    _prepare_complete_closure(tmp_path)
    review_path = tmp_path / "governance/reviews/independent_review.json"
    payload = json.loads(review_path.read_text(encoding="utf-8"))
    del payload["reviewed_active_defects_digest"]
    review_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert {"REVIEW-010", "REVIEW-013"} <= _review_codes(findings)


def test_closure_rejects_nonexistent_reviewed_commit(tmp_path: Path) -> None:
    reviewed_commit, reviewed_tree_digest, _original, _closure = _prepare_complete_closure(tmp_path)
    assert reviewed_commit != "f" * 40
    _write_review(
        tmp_path,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
        extra={
            "reviewed_commit": "f" * 40,
            "reviewed_active_defects_digest": "0" * 64,
        },
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-REVIEW-001" in _closure_codes(findings)


def test_closure_rejects_reviewed_commit_outside_current_history(
    tmp_path: Path,
) -> None:
    reviewed_commit, reviewed_tree_digest, _original, _closure = _prepare_complete_closure(
        tmp_path
    )
    reviewed_tree = _git(tmp_path, "rev-parse", f"{reviewed_commit}^{{tree}}")
    unrelated_reviewed_commit = _git(
        tmp_path,
        "commit-tree",
        reviewed_tree,
        "-m",
        "unrelated reviewed implementation",
    )
    _write_review(
        tmp_path,
        reviewed_commit=unrelated_reviewed_commit,
        reviewed_tree_digest=reviewed_tree_digest,
    )
    findings: list[GovernanceFinding] = []

    _audit_defects_and_review(tmp_path, findings)

    assert "DEFECT-REVIEW-002" in _closure_codes(findings)
