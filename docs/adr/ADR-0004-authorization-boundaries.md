# ADR-0004: Scope-bound semantic authorization

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

High-impact operations require a complete authorization decision binding actor/operator, action, resource, exact scope, current state, granted and denied authority, issuance, validity, reuse, revocation, reason, expected identity, stale-state rule, audit identity, audit event, and fail-closed posture.

A Boolean may be an additional caller confirmation but cannot itself grant authority. Operation-specific contracts may be stricter, including single-use authorization and exact replay rules.

## Current identity boundary

The current local CLI records an explicit operator identifier. This is audit identity, not authentication. Hosted authentication, delegation, impersonation, temporary access, elevation, and tenant isolation are mandatory entry conditions before a hosted GUI can be production-ready.

## Consequences

Generic editing, authority expansion, stale writes, destructive overwrite, automatic correction, recurrence, sending, credential substitution, and access-control bypass remain denied unless an explicit future capability contract and review establish otherwise.
