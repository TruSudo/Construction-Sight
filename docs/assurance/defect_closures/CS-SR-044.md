# CS-SR-044 Permanent Closure Evidence

Defect: `CS-SR-044 — trusted-time-authority`

## Historical root cause

Production-visible authorization and execution facades accept caller-controlled clocks or authorization timestamps, allowing an invented time to influence authorization validity, policy-date checks, date-scoped execution identity, and audit metadata.

## Resolution

Resolution implementation commit: `0f26546f8e415fdf37910b0b26d39bf2ca84dbae`

Resolution Git tree: `24b66aa15ad9b192347e8dba9322d3c0da5074c3`

Authoritative effect time is now acquired internally by ConstructionSight's owned effect-consumption boundary and bound into operation validity and audit state; production authorized services reject caller-selected clocks and authorization-time seams, while deterministic time substitution is restricted to tests and semantic certification treats clock parameters as prohibited dynamic authority.

## Regression evidence

The canonical evidence paths and regression tests recorded in `governance/resolved_defects.toml` exercise this boundary on the current remediation lineage. In particular, semantic authorization tests cover import/local aliases, spoofed authorized names and methods, unresolved authorized-looking calls, indirect effect selection, branch bypass, effect-before-authorization, swallowed authorization failure, validation ordering, interprocedural paths, direct-effect bypass, owned consumption, and production injection seams.

This closure preserves the original historical finding while permanently retiring its corrected root cause.
