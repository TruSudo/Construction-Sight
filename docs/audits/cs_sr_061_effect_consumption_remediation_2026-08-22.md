# CS-SR-061 effect-consumption remediation evidence

## Status

`CS-SR-061` remains active. This artifact records correction and regression evidence only; it does not claim independent review, certification, readiness, or closure.

## Correction boundary

ConstructionSight now owns one SQLite-backed protected-effect lifecycle:

1. canonical authorization is issued and independently validated;
2. trusted UTC time is acquired internally;
3. a stable reservation key and complete operation digest bind actor, action, resource, exact scope, current/expected state, revocation, allowance, content, owned implementation, and replay policy;
4. `BEGIN IMMEDIATE` plus a durable unique key atomically creates `reserved` state;
5. compare-and-swap changes the record to `in_progress` immediately before the owned effect;
6. terminal success retains canonical result JSON and its digest;
7. terminal failure retains phase, type, and failure digest; and
8. exact committed replay returns the retained result without invoking the effect.

Reserved, in-progress, failed, conflicting, single-use, stale, and unavailable-store states fail closed. No automatic recovery treats a crash-retained in-progress effect as absent.

Production authorized services no longer accept caller-selected ledgers, used-authorization-ID sets, clocks, executors, persisters, verifiers, or consumption backends. The semantic authorization certifier models decision, validation, and atomic-consumption phases and rejects both direct-effect bypass and production signature injection.

## Covered effect families

- CEQAnet listing, detail, CSV, governed per-UTC-date evidence, recurring attempts, and write-plan persistence;
- source readiness, verification checklist/evidence, promotion planning, and registry plan/apply;
- ArcGIS bounded probe and proof-bundle persistence;
- lead-workflow database transitions; and
- authoritative-result database mutations.

## Regression evidence

`tests/test_effect_consumption.py` covers sequential replay, thread concurrency, cross-process file/evidence behavior, restart, crash after effect start, pre-effect and post-start terminal failures, terminal-result persistence failure, unavailable storage, stale authorization, changed content, single-use denial, retained-result integrity, and production backend-injection rejection.

Service regressions cover CEQAnet UTC-date allowance across changed/stale series snapshots, recurring attempt sequence, detached write content, ArcGIS persistence, source-service exact replay, and concurrent real database writers. `tests/test_semantic_authorization_certification.py` proves validation alone cannot authorize an effect and that caller-selected consumption/time/effect seams are rejected.

Focused mutants protect reservation removal, check-then-act replacement, process-local state, duplicate recurring sequence, stale-series daily allowance reuse, replay re-execution, caller-ledger trust, terminal-state persistence, content-binding removal, stale authorization, and crash-state classification.

Final local Python 3.12.13 evidence on the candidate tree: exact-lock verification passed with 38 locked distributions and zero findings; `pip check`, deterministic SBOM generation, Ruff, strict mypy over 251 source files, compileall, adapter audit, and source-coverage audit passed; warning-strict pytest passed 1,263 tests; and focused mutation certification killed 59 of 59 mutants. Repository scanning produced zero repository findings and only the intentional governance blockers: 61 `DEFECT-ACTIVE-001` findings plus `REVIEW-001`.

## Remaining gates

The complete tree still requires exact-head Python 3.11 and 3.12 CI and fresh independent adversarial review. All active defects, including `CS-SR-061`, remain blockers.
