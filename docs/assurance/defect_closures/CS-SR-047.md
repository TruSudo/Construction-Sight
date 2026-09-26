# CS-SR-047 Permanent Closure Evidence

Defect: `CS-SR-047 — derived-identity-integrity`

## Resolution

The integrated resolution is bound to commit `6cd5c369b4c82abbcf678e971bc2c1f3376e7772` (tree `09fc0a45f1a25178cf04859928ec777ea3a3031b`).

Lead, contractor, artifact observation, fingerprint, and resolution-candidate identities are recomputed from canonical source content using versioned derivation rules and full SHA-256 identities where identity is evidentiary. Symmetric resolution pairs are canonicalized, and forged/stale normalized values and identifiers fail validation.

## Exact-head validation

Canonical pull-request CI run `36190987604` (#1543) executed against that exact commit. Retained Python 3.11 evidence reports **2134/2134 tests passed** and **164/164 focused mutants killed**. Retained Python 3.12 evidence independently reports **2134/2134 tests passed** and **164/164 focused mutants killed**. Ruff, strict mypy, compilation, adapter/source audits, Native assurance preflight, GitHub Actions provenance verification, repository/semantic certification, diff hygiene, and both isolated vulnerability audits passed. Repository certification contained only `ASSURANCE-001` plus the six then-active defect markers.

## Retained regression evidence

`tests/test_derived_identity_integrity.py`, `tests/test_artifact_resolution_service.py`, and `tests/test_lead_dedupe_models.py` retain forged-normalization, stale-ID, symmetric-pair, fingerprint and canonical-fixture regressions.

This closure preserves the historical finding and retires its corrected root cause. Final zero-active-defect Native Maximum Assurance remains a separate finalization transaction.
