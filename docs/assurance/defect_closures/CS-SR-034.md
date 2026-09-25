# CS-SR-034 Permanent Closure Evidence

Defect: `CS-SR-034 — semantic-authorization-proof`

## Historical root cause

The static semantic-authorization audit trusts authorized-looking function names without resolving imported or aliased call targets and proving that canonical authorization occurs before every reachable effect.

## Resolution

Resolution implementation commit: `b76be5c8d3a57ec68aeb4490b486c1802f66ba30`

Resolution Git tree: `ede507fe2df4107804f75b58d6e6b4d984674b4b`

Replaced authorized-looking-name trust with a resolved, path-sensitive interprocedural AST call graph that follows imports and aliases, tracks authorization phases, fails closed on unresolved authorized-looking calls and indirect effect selection, and proves canonical authorization/preflight and owned effect consumption dominate every reachable high-impact effect.

## Regression evidence

The canonical evidence paths and regression tests recorded in `governance/resolved_defects.toml` exercise this boundary on the current remediation lineage. In particular, semantic authorization tests cover import/local aliases, spoofed authorized names and methods, unresolved authorized-looking calls, indirect effect selection, branch bypass, effect-before-authorization, swallowed authorization failure, validation ordering, interprocedural paths, direct-effect bypass, owned consumption, and production injection seams.

This closure preserves the original historical finding while permanently retiring its corrected root cause.
