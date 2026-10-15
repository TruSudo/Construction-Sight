# CS-SR-050 Permanent Closure Evidence

Defect: `CS-SR-050 — business-transition-concurrency`

## Historical root cause

Lead workflow authorization could validate an expected current state and then persist through a non-conditional upsert, allowing competing processes to authorize the same prior state and overwrite one another.

## Resolution

Implementation commit: `a90615d23039a3b0ce5cf989ce6006f352825af6`

Resolution tree: `454bf65e924ea0a40fea8fcd68675cd6b1209acb`

The persisted workflow transition path now uses a database compare-and-swap bound to the exact workflow identity, expected status, and exact prior serialized payload. A stale or competing writer changes zero rows and is rejected. The successful transition appends exactly one event and verifies the exact updated projection after the conditional write.

## Regression and retained evidence

`tests/test_lead_workflow_storage.py` contains a deterministic competing-writer regression that commits the first transition and requires the second session, still holding the stale prior state, to fail. `tests/test_lead_workflow_transition_authorization.py` covers the authorization/state binding at the operator boundary. The current exact-head CI validates the integrated code before this closure is accepted.

This closure preserves the historical finding and retires the corrected root cause.
