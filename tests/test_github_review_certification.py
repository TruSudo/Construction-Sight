from __future__ import annotations

from typing import Any

import pytest

from constructionsight.github_review_certification import (
    build_report,
    parse_bound_reviewer,
    verify_github_review_binding,
)


def _report() -> dict[str, Any]:
    return {
        "schema_version": "constructionsight.assurance-review/v1",
        "assurance_mode": "independent_human",
        "independence_claim": "independent_human",
        "reviewer": "github:IndependentReviewer#4242",
        "reviewed_commit": "a" * 40,
        "pull_request_number": 117,
    }


def _github_review() -> dict[str, Any]:
    return {
        "id": 4242,
        "state": "APPROVED",
        "commit_id": "a" * 40,
        "user": {
            "login": "IndependentReviewer",
            "type": "User",
        },
    }


def _github_pull_request() -> dict[str, Any]:
    return {
        "number": 117,
        "user": {"login": "TruSudo", "type": "User"},
    }


def _findings(
    report: dict[str, Any] | None = None,
    review: dict[str, Any] | None = None,
    pull_request: dict[str, Any] | None = None,
    *,
    repository_owner: str = "TruSudo",
) -> tuple[str, ...]:
    return verify_github_review_binding(
        report or _report(),
        review or _github_review(),
        pull_request or _github_pull_request(),
        repository_owner=repository_owner,
    )


def test_parse_bound_reviewer_returns_login_and_review_id() -> None:
    assert parse_bound_reviewer("github:IndependentReviewer#4242") == (
        "IndependentReviewer",
        4242,
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "IndependentReviewer",
        "github:#4242",
        "github:IndependentReviewer#0",
        "github:-reviewer#4242",
        "github:reviewer-#4242",
    ],
)
def test_parse_bound_reviewer_rejects_malformed_values(value: object) -> None:
    with pytest.raises(ValueError):
        parse_bound_reviewer(value)


def test_valid_independent_human_review_binding_passes() -> None:
    assert _findings() == ()


def test_native_or_external_model_mode_cannot_claim_human_approval() -> None:
    report = _report()
    report["assurance_mode"] = "native_maximum"
    report["independence_claim"] = "native_context_isolated_not_independent"

    assert "GitHub approval only verifies independent_human assurance mode" in _findings(
        report=report
    )


def test_pr_author_cannot_self_certify() -> None:
    report = _report()
    report["reviewer"] = "github:TruSudo#4242"
    review = _github_review()
    review["user"] = {"login": "TruSudo", "type": "User"}

    assert "independent reviewer must differ from the PR author" in _findings(
        report,
        review,
    )


def test_repository_owner_cannot_self_certify() -> None:
    report = _report()
    report["reviewer"] = "github:RepositoryOwner#4242"
    review = _github_review()
    review["user"] = {"login": "RepositoryOwner", "type": "User"}

    assert "independent reviewer must differ from the repository owner" in _findings(
        report,
        review,
        repository_owner="RepositoryOwner",
    )


def test_review_must_be_approved() -> None:
    review = _github_review()
    review["state"] = "COMMENTED"

    assert "GitHub review state must be APPROVED" in _findings(review=review)


def test_review_and_pull_request_ids_must_match_artifact() -> None:
    review = _github_review()
    review["id"] = 9999
    pull_request = _github_pull_request()
    pull_request["number"] = 118
    findings = _findings(review=review, pull_request=pull_request)

    assert "GitHub review ID does not match the assurance binding" in findings
    assert "GitHub pull request does not match the assurance binding" in findings


def test_reviewer_login_must_match_artifact_binding() -> None:
    review = _github_review()
    review["user"] = {"login": "SomeoneElse", "type": "User"}

    assert "GitHub reviewer login does not match the assurance binding" in _findings(
        review=review
    )


def test_bot_identity_cannot_satisfy_independent_human_review() -> None:
    review = _github_review()
    review["user"] = {"login": "IndependentReviewer", "type": "Bot"}

    assert "independent GitHub reviewer must be a human User identity" in _findings(
        review=review
    )


def test_review_commit_must_match_reviewed_commit() -> None:
    review = _github_review()
    review["commit_id"] = "c" * 40

    assert "GitHub review commit does not match reviewed_commit" in _findings(
        review=review
    )


def test_report_is_deterministic_and_exposes_source_identities() -> None:
    report = build_report(
        _report(),
        _github_review(),
        _github_pull_request(),
        repository_owner="TruSudo",
    )

    assert report == {
        "schema_version": "constructionsight.github-review-certification/v1",
        "passed": True,
        "reviewer": "github:IndependentReviewer#4242",
        "reviewed_commit": "a" * 40,
        "pull_request_number": 117,
        "github_review_id": 4242,
        "findings": [],
    }
