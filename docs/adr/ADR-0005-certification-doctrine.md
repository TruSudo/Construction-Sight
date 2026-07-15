# ADR-0005: Exact-tree semantic certification and independent review

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

The canonical certifier combines repository hygiene with semantic governance. It emits deterministic versioned JSON and stable finding codes for architecture, capability traceability, dependency identity and locks, Action pins, network boundaries, authorization classification, adversarial-test obligations, active defects, and independent review.

Malformed governance, unsupported schemas, missing controls, active defects, and code/contract disagreement fail closed. The exact certified commit must be the reviewed tree plus only the structured final review, resolved-ledger, and final-audit evidence allowed by the review-binding rule.

High-risk changes require a separately initiated adversarial review. The report must seek alternate bypasses, stale-state and replay failures, concurrency failures, fail-open behavior, supply-chain defects, overclaimed documentation, mirrored tests, missing negative cases, architecture circumvention, and gaps in certification itself.

## Consequences

A green formatter, type checker, test suite, or legacy certifier is insufficient by itself. A review summary that repeats implementation claims is insufficient. Certification cannot pass while active defects or unresolved review findings remain.
