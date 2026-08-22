from __future__ import annotations

from pathlib import Path


def _workflow() -> str:
    return Path(".github/workflows/ci.yml").read_text(encoding="utf-8")


def test_ci_checks_out_and_enforces_exact_event_head() -> None:
    workflow = _workflow()
    expected_sha = "${{ github.event.pull_request.head.sha || github.sha }}"

    assert f"ref: {expected_sha}" in workflow
    assert "fetch-depth: 0" in workflow
    assert "Resolution ancestry certification requires the complete reviewed history." in workflow
    assert "name: Verify exact checkout" in workflow
    assert f"EXPECTED_SHA: {expected_sha}" in workflow
    assert 'test "${actual}" = "${EXPECTED_SHA}"' in workflow
    assert "'${{ steps.checkout-identity.outcome }}'" in workflow


def test_ci_revalidates_only_claimed_independent_human_review() -> None:
    workflow = _workflow()

    assert "pull-requests: read" in workflow
    assert "name: Verify optional independent human GitHub review" in workflow
    assert "id: github-review" in workflow
    assert "constructionsight.assurance_certification mode" in workflow
    assert "'independent_human'" in workflow
    assert "constructionsight.assurance_certification pull-request-number" in workflow
    assert "constructionsight.github_review_certification review-id" in workflow
    assert "pulls/{pr_number}" in workflow
    assert "pulls/{pr_number}/reviews/{review_id}" in workflow
    assert "constructionsight.github_review_certification verify" in workflow
    assert "--github-pull-request" in workflow
    assert "REPOSITORY_OWNER: ${{ github.repository_owner }}" in workflow
    assert "'${{ steps.github-review.outcome }}'" in workflow
    assert (
        "Assurance artifact absent; repository certification remains blocking." in workflow
    )
    assert "makes no independent-human claim" in workflow
