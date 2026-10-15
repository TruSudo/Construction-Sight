# CS-SR-052 Permanent Closure Evidence

Defect: `CS-SR-052 — result-ledger-content-identity`

## Historical root cause

Result-ledger identity was derived primarily from workflow/status/revision metadata and
did not bind every semantically material outcome field. Distinct result contents could
therefore share the same nominal ledger identity, weakening authority/event provenance.

## Resolution

Resolution implementation commit:

`de1007dd04300b521b1b6ad5713b98ab82b11ddc`

Resolution Git tree:

`a9c7c4f1a1d3221acb875550e0c82deff7df5d76`

The corrected implementation:

- defines a full canonical SHA-256 content digest over material result-ledger outcome
  content;
- recomputes and validates that digest at model/history boundaries;
- keeps revision/head identity distinct from content identity;
- binds authority events to predecessor/current content digests;
- includes those content digests in authority-event identity; and
- rejects post-validation material mutation or authority-event digest tampering.

## Regression evidence

Canonical regression coverage includes:

- `tests/test_result_ledger_service.py`
  - `test_materially_different_results_have_distinct_content_digests`
  - `test_content_digest_rejects_post_validation_material_mutation`
- `tests/test_result_authority_event_integrity.py`
  - `test_authority_event_must_bind_exact_ledger_content_digest`

Implementation evidence includes:

- `src/constructionsight/result_ledger_models.py`
- `src/constructionsight/result_ledger_service.py`
- `src/constructionsight/result_authority_models.py`
- `src/constructionsight/result_authority_service.py`

## Validation

The original remediation head was validated by CI run `36111874704`: both isolated
vulnerability audits passed and both Python quality matrices passed all substantive
checks, failing only the aggregate active-defect enforcement step.

The remediation has since been merged only into the non-main
`assurance/permanent-resolution-integration` branch. Final ledger transition is
conditioned on successful substantive validation of that combined exact head.

This closure preserves the historical finding while permanently retiring the corrected
root cause. It does not claim resolution of CS-SR-053 financial-decimal integrity.
