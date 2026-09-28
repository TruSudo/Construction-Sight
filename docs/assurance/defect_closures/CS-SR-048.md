# CS-SR-048 Permanent Closure Evidence

Defect: `CS-SR-048 — operational-confidence-gating`

## Historical root cause

Opportunity and readiness logic could assign full operational weight to evidence merely because a signal was present while treating confidence as descriptive metadata. Low-confidence, inferred, ambiguous, or zero-confidence inputs could therefore accumulate enough nominal score to reach an actionable state.

## Resolution

Resolution implementation commit:

`13e4ebf9befbac90154110b315e855ba6b2d31dd`

Resolution Git tree:

`aaf777d2ab495eefc5e39dc9a336800c2080cc74`

The corrected implementation:

- computes each signal's operational contribution as its configured weight multiplied by confidence;
- makes zero-confidence signals contribute zero operational points;
- recomputes aggregate confidence and confidence-weighted lead score at the report model boundary rather than trusting caller assertions;
- adds a versioned minimum actionable-confidence threshold to the opportunity scoring profile;
- prevents a high nominal score with insufficient aggregate confidence from reaching outreach-preview readiness; and
- preserves explicit review/monitor/hold states for evidence that is too weak to act on.

## Regression evidence

Canonical regression coverage includes:

- `tests/test_opportunity_enrichment_models.py`
  - rejects caller-forged unweighted scores;
  - rejects caller-forged aggregate confidence; and
  - proves confidence-weighted operational contribution.
- `tests/test_opportunity_enrichment_service.py`
  - proves low-confidence high-weight evidence remains review-bound;
  - proves zero-confidence evidence contributes no operational score; and
  - verifies revised cross-signal scoring and next-action semantics.

Implementation evidence includes:

- `src/constructionsight/opportunity_enrichment_models.py`
- `src/constructionsight/opportunity_enrichment_service.py`
- `src/constructionsight/opportunity_scoring_profile.py`
- `docs/architecture/opportunity_enrichment_spine.md`

## Validation

The current-line remediation exact head `13e4ebf9befbac90154110b315e855ba6b2d31dd` was validated by GitHub Actions run `36120970387`.

Both Python 3.11 and 3.12 isolated vulnerability audits passed. Both quality matrices passed exact checkout, dependency integrity, deterministic SBOM, Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, repository/semantic certification, diff hygiene, and environment-identity checks. The only failing step was the aggregate `Enforce all quality gates` step because other active defects remained.

The validated remediation was then merged only into the non-main permanent-resolution line at `22ff17f177fc26d9056f2678cc18f4c9ad4894eb`, while CS-SR-048 was still active, satisfying the incremental closure invariant.

This closure preserves the historical finding while permanently retiring the corrected root cause.
