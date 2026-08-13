from __future__ import annotations

from pathlib import Path


def test_ci_checks_out_and_enforces_exact_event_head() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    expected_sha = "${{ github.event.pull_request.head.sha || github.sha }}"

    assert f"ref: {expected_sha}" in workflow
    assert "fetch-depth: 2" in workflow
    assert "name: Verify exact checkout" in workflow
    assert f"EXPECTED_SHA: {expected_sha}" in workflow
    assert 'test "${actual}" = "${EXPECTED_SHA}"' in workflow
    assert "'${{ steps.checkout-identity.outcome }}'" in workflow
