# CS-SR-007 Permanent Closure Evidence

Defect: `CS-SR-007 — independent-review`

## Historical root cause

High-risk changes lacked a mandatory structured adversarial review artifact bound to the exact reviewed implementation, allowing review obligations to remain informal or disconnected from unresolved findings.

## Resolution

Implementation commit: `65b2ef5e726d8ab810776d1774edc74b1b70bc4c`

Resolution tree: `0930ed4c5e9ffe508e8677b1d311f38606bc2a52`

ConstructionSight replaced an escapable high-risk-only review requirement with the stronger Native Maximum Assurance baseline for every final candidate. The canonical assurance contract requires a structured artifact, an exact commit and exact covered-tree binding, multiple distinct context-isolated adversarial passes, a blind candidate union, and zero unresolved or deferred candidates. Because every final candidate receives the stricter treatment, a separate classifier cannot exempt a high-risk change from review. The doctrine also distinguishes native review from genuinely independent external-model or unrelated-human review rather than making a false independence claim.

## Regression and retained evidence

`tests/test_assurance_certification.py`, `tests/test_assurance_reviewed_tree_binding.py`, and `tests/test_review_binding_certification.py` enforce exact-tree binding, complete pass/candidate accounting, and fail-closed unresolved-candidate behavior. `governance/assurance_contract.toml` declares zero unresolved/deferred candidates and mandatory exact commit/tree binding.

This closure retires the missing structured exact-head review mechanism. It does not assert that the current branch has already completed its final Native Maximum Assurance transaction.
