# ADR-0001: Machine-enforced architecture contract

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

The tracked production tree is governed by `governance/architecture_contract.toml` and an AST-based certifier. Every module must belong to exactly one layer. Internal imports, cycles, and acquisition of network, persistence, filesystem-mutation, subprocess, operator, and authority-bearing capabilities are checked against that layer.

Exceptions are exact, expiring, owned, risk-documented, test-backed, and ADR-linked. Documentation alone is not an architecture control.

## Consequences

New modules fail certification until classified. Refactoring that creates reverse dependencies or utility bypasses fails before merge. The initial contract is intentionally strict and may reveal legacy edges; those defects must be corrected or narrowly excepted rather than hidden.
