from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from constructionsight.authority_certification import (
    _audit_defects_and_review,
    _reviewed_tree_digest,
)
from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.owner_acceptance_certification import (
    assurance_evidence_digest,
    expected_acceptance_body,
    expected_review_method,
    verify_github_owner_acceptance,
)
from tests.support.assurance import (
    git,
    initialize_repository,
    rewrite_assurance,
    write_assurance,
)


def _report(root: Path) -> dict[str, Any]:
    initialize_repository(root)
    reviewed_commit = git(root, "rev-parse", "HEAD")
    return write_assurance(
        root,
        reviewed_commit=reviewed_commit,
        reviewed_tree_digest=_reviewed_tree_digest(root),
    )


def _sources(
    report: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    review = {
        "id": 5151,
        "state": "COMMENTED",
        "author_association": "OWNER",
        "user": {"login": "TestOwner", "type": "User"},
        "commit_id": report["reviewed_commit"],
        "body": expected_acceptance_body(report),
        "submitted_at": "2026-09-14T19:00:00Z",
    }
    pull_request = {"number": 117}
    return review, pull_request


def _audit(root: Path) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    _audit_defects_and_review(root, findings)
    return findings


def test_owner_acceptance_evidence_digest_is_stable_and_material() -> None:
    report: dict[str, Any] = {
        "schema_version": "constructionsight.assurance-review/v1",
        "status": "passed",
        "assurance_mode": "native_maximum",
        "independence_claim": "native_context_isolated_not_independent",
        "reviewed_commit": "1" * 40,
        "reviewed_active_defects_digest": "2" * 64,
        "reviewed_tree_digest": "3" * 64,
        "pull_request_number": None,
        "surviving_security_mutants": 0,
        "passes": [],
        "candidate_union": {"artifact_sha256": "4" * 64},
        "quality_gates": [],
        "limitations": ["no_independent_external_model_or_human_review"],
        "owner": "unbound",
        "owner_acceptance": True,
        "reviewer": "unbound",
        "review_method": "unbound",
    }
    digest = assurance_evidence_digest(report)
    rebound = deepcopy(report)
    rebound["owner"] = "github:Someone@pr-1#2"
    rebound["reviewer"] = rebound["owner"]
    rebound["review_method"] = "later"

    assert assurance_evidence_digest(rebound) == digest

    changed = deepcopy(report)
    changed["surviving_security_mutants"] = 1
    assert assurance_evidence_digest(changed) != digest


def test_authenticated_owner_acceptance_passes(tmp_path: Path) -> None:
    report = _report(tmp_path)
    review, pull_request = _sources(report)

    findings = verify_github_owner_acceptance(
        report,
        review,
        pull_request,
        repository_owner="TestOwner",
    )

    assert findings == ()


def test_owner_acceptance_rejects_spoofed_owner(tmp_path: Path) -> None:
    report = _report(tmp_path)
    review, pull_request = _sources(report)

    findings = verify_github_owner_acceptance(
        report,
        review,
        pull_request,
        repository_owner="DifferentOwner",
    )

    assert "bound assurance owner is not the repository owner" in findings


def test_owner_acceptance_rejects_stale_commit(tmp_path: Path) -> None:
    report = _report(tmp_path)
    review, pull_request = _sources(report)
    review["commit_id"] = "f" * 40

    findings = verify_github_owner_acceptance(
        report,
        review,
        pull_request,
        repository_owner="TestOwner",
    )

    assert (
        "GitHub owner review commit does not match reviewed_commit"
        in findings
    )


def test_owner_acceptance_rejects_changed_evidence(tmp_path: Path) -> None:
    report = _report(tmp_path)
    review, pull_request = _sources(report)
    report["surviving_security_mutants"] = 1

    findings = verify_github_owner_acceptance(
        report,
        review,
        pull_request,
        repository_owner="TestOwner",
    )

    assert (
        "review_method does not bind the exact material assurance evidence digest"
        in findings
    )
    assert (
        "GitHub owner acceptance body does not match exact assurance evidence"
        in findings
    )


def test_owner_acceptance_rejects_wrong_body_state_or_association(
    tmp_path: Path,
) -> None:
    report = _report(tmp_path)
    review, pull_request = _sources(report)
    review["body"] = "accepted"
    review["state"] = "APPROVED"
    review["author_association"] = "MEMBER"

    findings = verify_github_owner_acceptance(
        report,
        review,
        pull_request,
        repository_owner="TestOwner",
    )

    assert (
        "GitHub owner acceptance transport state must be COMMENTED"
        in findings
    )
    assert (
        "GitHub owner acceptance must have OWNER author association"
        in findings
    )
    assert (
        "GitHub owner acceptance body does not match exact assurance evidence"
        in findings
    )


def test_canonical_governance_rejects_unbound_owner(tmp_path: Path) -> None:
    report = _report(tmp_path)
    report["owner"] = "owner:test"
    report["reviewer"] = "owner:test"
    report["review_method"] = expected_review_method(report)
    rewrite_assurance(tmp_path, report)

    findings = _audit(tmp_path)

    assert "ASSURANCE-029" in {finding.code for finding in findings}
