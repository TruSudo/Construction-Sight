# CS-SR-046 Permanent Closure Evidence

Defect: `CS-SR-046 — epistemic-provenance-authority`

## Resolution

The integrated resolution is bound to commit `6cd5c369b4c82abbcf678e971bc2c1f3376e7772` (tree `09fc0a45f1a25178cf04859928ec777ea3a3031b`).

Generic provenance no longer accepts caller-authored verified/confidence authority. Confidence is derived from an explicit evidence-backed basis, generic provenance cannot self-certify verification, evidence digest and lineage are computed projections, and persistence/replay uses authoritative declared fields rather than accepting computed epistemic claims as input.

## Exact-head validation

Canonical pull-request CI run `36190987604` (#1543) executed against that exact commit. Retained Python 3.11 evidence reports **2134/2134 tests passed** and **164/164 focused mutants killed**. Retained Python 3.12 evidence independently reports **2134/2134 tests passed** and **164/164 focused mutants killed**. Ruff, strict mypy, compilation, adapter/source audits, Native assurance preflight, GitHub Actions provenance verification, repository/semantic certification, diff hygiene, and both isolated vulnerability audits passed. Repository certification contained only `ASSURANCE-001` plus the six then-active defect markers.

## Retained regression evidence

`tests/test_provenance_authority.py`, `tests/test_ceqanet_persistence_preview.py`, and `tests/test_source_candidate_docket.py` cover self-asserted authority, evidence-derived confidence, persistence payloads, and replay validation.

This closure preserves the historical finding and retires its corrected root cause. Final zero-active-defect Native Maximum Assurance remains a separate finalization transaction.
