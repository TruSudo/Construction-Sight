# Phase 6 — CEQAnet Live Read-Only Adapter Plan

## Status

Phase 6 begins with CEQAnet as the first live read-only adapter candidate.

## Why CEQAnet First

CEQAnet is the lowest-friction high-value public source for early construction intelligence.

It exposes CEQA environmental review records before many projects reach local permitting portals.

## Public Surface Confirmed

The CEQAnet portal is publicly reachable and redirects to:

```text
https://ceqanet.lci.ca.gov/
```

The public advanced search page is available at:

```text
https://ceqanet.lci.ca.gov/Search/Advanced
```

The advanced search page exposes public search concepts including:

- SCH Number
- date range
- document type
- lead/public agency

## Implementation Order

The CEQAnet adapter must be built in this order:

1. fixture-backed parser
2. normalization into `CeqaRecord`
3. provenance capture
4. adapter contract integration
5. no-network tests
6. live read-only HTTP discovery
7. conservative source query support
8. live smoke test command

## Legal Boundary

The adapter must remain lawful and read-only.

Do not bypass authentication, captchas, rate limits, access controls, paywalls, robots restrictions, or terms-of-service limits.

Do not use credentials.

Do not scrape private data.

## Phase 6 Initial Constraint

Start with fixture-backed parsing before live collection so the normalization path is deterministic and auditable.
