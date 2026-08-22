# ADR-0004: Scope-bound semantic authorization

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

High-impact operations require a complete authorization decision binding actor/operator, action, resource, exact scope, current state, granted and denied authority, issuance, validity, reuse, revocation, reason, expected identity, stale-state rule, audit identity, audit event, and fail-closed posture.

A Boolean may be an additional caller confirmation but cannot itself grant authority. Validation does not consume authority. Immediately before a protected effect, the application must enter the private ConstructionSight-owned consumption boundary, which atomically reserves a stable operation allowance in durable state. Production callers cannot provide clocks, ledgers, used-ID snapshots, stores, executors, persisters, or verifiers to this boundary.

The reservation key binds actor, action, resource, and stable allowance. Its operation digest additionally binds the logical authorization, exact scope, expected/current state, revocation identity, content, owned implementation, and replay policy. A committed exact replay returns the retained result without invoking the effect. Reserved, in-progress, failed, conflicting, missing-store, and single-use duplicates fail closed. Crash recovery never assumes an in-progress effect did not happen.

Repository certification resolves tracked call targets from every high-impact operator entry point instead of trusting authorized-looking names. It follows imported, re-exported, local, module-level, and class-method aliases across application functions, preserves decision, validation, and consumption phases along reachable control-flow paths, and rejects any direct effect that bypasses the owned atomic runner. It also rejects production authorized-service signatures that expose caller-selected effect, time, or consumption state. Indirect callable selection or an unresolved authorized-looking service fails closed.

## Current identity boundary

The current local CLI records an explicit operator identifier. This is audit identity, not authentication. Hosted authentication, delegation, impersonation, temporary access, elevation, and tenant isolation are mandatory entry conditions before a hosted GUI can be production-ready.

## Consequences

Generic editing, authority expansion, stale writes, destructive overwrite, automatic correction, recurrence, sending, credential substitution, and access-control bypass remain denied unless an explicit future capability contract and review establish otherwise.
