# CS-SR-054 Permanent Closure Evidence

Defect: `CS-SR-054 — runtime-evidence-containment`

## Resolution

The integrated containment implementation is bound to commit `62d747172892adb9be24a4d331428080edd91ad2` (tree `1225a6fe9f94a164609654cd467994fb35fef2ab`).

Runtime evidence and output access is centralized in `src/constructionsight/storage/runtime_artifacts.py`. Canonical names are validated before interpretation; parent directories are opened and pinned descriptor-relatively; `O_NOFOLLOW`, directory-relative stat/open primitives, and same-entry checks reject symlink or ancestor substitution; unsupported platforms fail closed for security-sensitive access; bounded reads consume the same opened handle that was checked; and publication uses contained staging and atomic directory-relative replacement/link semantics with durability checks.

The loader and output batches retain before/after evidence in `docs/audits/evidence/2026-09-21-loader-batch/` and `docs/audits/evidence/2026-09-21-output-batch/`.

## Regression evidence

Canonical tests cover absolute and parent references, platform aliases, symlinked ancestors and final targets, descriptor swaps, verify/use races, bounded same-handle reads, contained publication, and output replacement behavior. Exact-head quality matrices continue to execute these tests.

This closure preserves the historical finding and retires the runtime evidence containment root cause.
