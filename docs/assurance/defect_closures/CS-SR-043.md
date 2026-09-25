# CS-SR-043 Permanent Closure Evidence

Defect: `CS-SR-043 — effect-implementation-authority`

## Historical root cause

Production-visible application and execution services can authorize an operation and then invoke caller-selected effect implementations such as executors, persisters, HTTP checkers, registries, adapters, or equivalent callbacks, so the implementation that performs the effect is not necessarily the implementation whose authority was reviewed.

## Resolution

Resolution implementation commit: `0f26546f8e415fdf37910b0b26d39bf2ca84dbae`

Resolution Git tree: `24b66aa15ad9b192347e8dba9322d3c0da5074c3`

Production authorization facades now execute effects only through ConstructionSight-owned concrete services and the durable effect-consumption boundary; caller-selected executors, persisters, HTTP clients/checkers, registries, adapters, ledgers and equivalent implementation seams are rejected from authorized production signatures and by semantic certification, while deterministic substitutes remain behind test-only seams.

## Regression evidence

The canonical evidence paths and regression tests recorded in `governance/resolved_defects.toml` exercise this boundary on the current remediation lineage. In particular, semantic authorization tests cover import/local aliases, spoofed authorized names and methods, unresolved authorized-looking calls, indirect effect selection, branch bypass, effect-before-authorization, swallowed authorization failure, validation ordering, interprocedural paths, direct-effect bypass, owned consumption, and production injection seams.

This closure preserves the original historical finding while permanently retiring its corrected root cause.
