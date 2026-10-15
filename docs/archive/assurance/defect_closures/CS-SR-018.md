# CS-SR-018 Permanent Closure Evidence

Defect: `CS-SR-018 — network-authorization-architecture`

## Historical root cause

Multiple live CLI paths import approved transport modules directly and use bare Boolean flags such as --execute-live as the operative network grant, bypassing canonical application services and the general scope-bound authorization decision contract.

## Resolution

Resolution implementation commit: `0f26546f8e415fdf37910b0b26d39bf2ca84dbae`

Resolution Git tree: `24b66aa15ad9b192347e8dba9322d3c0da5074c3`

The repository now mechanically forbids CLI-to-transport imports through the architecture contract, routes live operations through application/operator services, and path-sensitively requires canonical scope-bound authorization plus durable owned effect consumption before reachable network or persistence effects; Boolean confirmation remains an additional gate rather than operative authority.

## Regression evidence

The canonical evidence paths and regression tests recorded in `governance/resolved_defects.toml` exercise this boundary on the current remediation lineage. In particular, semantic authorization tests cover import/local aliases, spoofed authorized names and methods, unresolved authorized-looking calls, indirect effect selection, branch bypass, effect-before-authorization, swallowed authorization failure, validation ordering, interprocedural paths, direct-effect bypass, owned consumption, and production injection seams.

This closure preserves the original historical finding while permanently retiring its corrected root cause.
