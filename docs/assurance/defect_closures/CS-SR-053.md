# CS-SR-053 Permanent Closure Evidence

Defect: `CS-SR-053 — financial-decimal-integrity`

## Historical root cause

Result-share and royalty accounting accepted decimal-looking inputs but performed monetary arithmetic with binary floating point and implicit `round(..., 2)` behavior.

## Resolution

Implementation commit: `30b911d0fa01c5dff84d99b2c8ed98a396bbc744`

Resolution tree: `c6f0f492bc47e082e48561b92c913c9f544d6373`

The result ledger now converts money to exact integer minor units and share rates to exact millionths, enforces bounded decimal scales, calculates shares with explicit round-half-even integer arithmetic, derives share identity from exact units, persists exact minor-unit/rate columns, and rejects disagreement between the exact arithmetic and legacy display projections. The follow-up commit repairs canonical root-ledger construction and ensures the normalized monetary projection is what enters the validated result record.

## Regression and retained evidence

`tests/test_result_ledger_precision.py` protects cents/rate precision and identity behavior. `tests/test_result_ledger_service.py`, `tests/test_result_ledger_share_state.py`, and `tests/test_lead_workflow_storage.py` exercise calculation, replay, persistence, and share-state behavior. Exact-head CI is required to prove the integrated financial path is regression-clean.

This closure preserves the historical finding and retires the corrected root cause.
