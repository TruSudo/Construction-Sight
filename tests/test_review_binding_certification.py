from __future__ import annotations

import json
import subprocess
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
        "schema_version = \"constructionsight.active-defects/v1\"\n"
        "certification_requires_zero = true\n"
        "defects = []\n",
    )
    _write(
        root,
        "governance/resolved_defects.toml",
        "schema_version = \"constructionsight.resolved-defects/v1\"\n"
        "defects = []\n",
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
        "schema_version = \"constructionsight.active-defects/v1\"\n"
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
