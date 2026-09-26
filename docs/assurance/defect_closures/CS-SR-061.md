# CS-SR-061 Permanent Closure Evidence

Defect: `CS-SR-061 — effect-consumption-atomicity`

## Historical root cause

Protected effects could determine use availability from caller-selected or stale state without a ConstructionSight-owned atomic reservation, allowing one logical authorization or allowance to produce multiple effects.

## Resolution

Implementation commit: `0f26546f8e415fdf37910b0b26d39bf2ca84dbae`

Resolution tree: `24b66aa15ad9b192347e8dba9322d3c0da5074c3`

ConstructionSight now owns a durable SQLite-backed lifecycle that binds the exact operation, scope, expected/current state, trusted time, content, and owned implementation. `BEGIN IMMEDIATE` plus a unique reservation key creates the reservation atomically; compare-and-swap advances it immediately before effect execution; terminal success/failure is durable; and permitted exact replay returns the prior committed result without repeating the effect. Production paths reject caller-selected ledgers, clocks, executors, persisters, and consumption backends.

## Regression and retained evidence

The retained audit `docs/audits/cs_sr_061_effect_consumption_remediation_2026-08-22.md` records sequential, concurrent, cross-process, restart, stale-authorization, changed-content, duplicate-sequence, terminal-failure and replay coverage. `tests/test_effect_consumption.py` and `tests/test_semantic_authorization_certification.py` remain in the canonical suite.

Exact-head CI run `36122444501` subsequently passed the substantive Python 3.11/3.12 quality, test, mutation, preflight, source and vulnerability gates; remaining aggregate failure was ledger/final-assurance state rather than CS-SR-061.

This closure preserves the historical finding and retires the corrected root cause.
