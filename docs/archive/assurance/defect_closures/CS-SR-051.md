# CS-SR-051 Permanent Closure Evidence

Defect: `CS-SR-051 — historical-ledger-separation`

## Historical root cause

Records representing workflow events and historical transitions could be rewritten through update/upsert semantics, conflating mutable current-state projections with append-only historical evidence.

## Resolution

Implementation commit: `a90615d23039a3b0ce5cf989ce6006f352825af6`

Resolution tree: `454bf65e924ea0a40fea8fcd68675cd6b1209acb`

Workflow events are now append-only: an exact replay is idempotent, while any attempted rewrite of an existing event identity is rejected. Current workflow state remains a mutable projection updated through compare-and-swap, while transition evidence is separately retained as immutable event rows.

## Regression and retained evidence

`tests/test_lead_workflow_storage.py` proves exact event replay succeeds, changed historical payloads fail, competing transitions cannot replace history, and the committed event chain remains reconstructable. Existing result-ledger supersession tests separately preserve append-only outcome history.

This closure preserves the historical finding and retires the corrected root cause.
