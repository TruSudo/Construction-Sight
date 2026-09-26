# CS-SR-049 Permanent Closure Evidence

Defect: `CS-SR-049 — duplicate-review-gate`

## Historical root cause

A lead marked duplicate REVIEW_NEEDED could remain or become actionable because duplicate
uncertainty was treated primarily as a limitation. READY-to-ACTIVE and other actionable
transitions could proceed without proving the durable duplicate-review state had been
resolved.

## Resolution

Resolution implementation commit:

`ceea88953af6eb39a49717946934d7abe64b59b5`

Resolution Git tree:

`5f69c77b9dbbbda9ef3baf0cf2415d0aaf204f6e`

The complete correction lineage also includes:

- `fe5fabc0cd78f313ac7bfcf940f61895c8f940c1` — blocks unresolved duplicate
  review from actionable workflow states and adds concurrency/mutation regressions.
- `e3d72015a497446dd2c896eb693d6572294b3a91` — enforces durable candidate-level
  duplicate review across fingerprint drift, direct writes, and immutable duplicate
  result persistence.
- `ceea88953af6eb39a49717946934d7abe64b59b5` — retains immutable duplicate
  verdict semantics across safe rescans.

The corrected behavior:

- unresolved duplicate-review states initialize as non-actionable review/hold states;
- READY, ACTIVE, PAUSED, and CLOSED_SUCCESS are rejected while duplicate review is
  unresolved;
- persisted duplicate results are checked independently of transient fingerprint drift;
- direct workflow persistence cannot bypass the duplicate-review invariant;
- duplicate-result rows cannot be silently rewritten from unresolved to unique;
- authorized transitions recheck durable duplicate state before reserving or applying
  effects; and
- concurrent transition attempts remain non-actionable.

## Regression evidence

Canonical regression coverage includes:

- `tests/test_lead_workflow_models.py`
- `tests/test_lead_workflow_service.py`
- `tests/test_lead_workflow_storage.py`
- `tests/test_lead_workflow_transition_authorization.py`

The mutation contract includes dedicated witnesses for initial review status,
actionability, durable duplicate lookup, candidate-scoped duplicate state, immutable
duplicate-result persistence, and direct-storage bypass.

## Exact-head validation

The correction commits are ancestors of the validated integrated closure head
`c8482d7e8382b023fdb7f1ebea04df50ad574fef`.

CI run `36116152927` validated that head on Python 3.11 and Python 3.12. Ruff, mypy,
compileall, full pytest, focused mutation certification, adapter/source audits,
assurance preflight, repository/semantic certification, diff hygiene, environment
identity checks, and both isolated vulnerability audits passed. The only failing step
was the aggregate gate that intentionally rejects the remaining active defect ledger.

This closure records permanent resolution of CS-SR-049 while preserving the historical
finding and all remaining active blockers.
