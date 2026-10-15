# CS-SR-027 Permanent Closure Evidence

Defect: `CS-SR-027 — independent-review-identity-authenticity`

## Historical root cause

A repository-authored review artifact could name an arbitrary reviewer and satisfy the mechanical review gate without proving that a real independent GitHub reviewer submitted an approval on the exact reviewed commit.

## Resolution

Implementation commit: `65b2ef5e726d8ab810776d1774edc74b1b70bc4c`

Resolution tree: `0930ed4c5e9ffe508e8677b1d311f38606bc2a52`

When independent-human assurance is claimed, the assurance artifact must bind a GitHub login, positive review ID, pull-request number, and exact reviewed commit. Canonical CI re-fetches GitHub evidence and requires APPROVED state, the exact bound review ID and commit, a human User identity, and a reviewer distinct from both the pull-request author and repository owner. Native assurance does not make an independence claim and therefore cannot use a fabricated reviewer string to claim human independence.

## Regression and retained evidence

`tests/test_github_review_certification.py` covers spoofed reviewer identity, self-review by the PR author, repository-owner self-certification, wrong review/PR IDs, wrong commit, non-approved state, and bot identities. `tests/test_ci_exact_head_contract.py` protects the canonical CI wiring.

This closure preserves the historical finding and retires the identity-spoofing mechanism.
