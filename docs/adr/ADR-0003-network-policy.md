# ADR-0003: Complete policy for every network path

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

Every production network client must live in an approved transport module and have exactly one complete entry in `governance/network_contract.toml`. Application and domain code use explicit transport interfaces rather than importing clients directly.

Policies distinguish transport failure, timeout, retryable and terminal status, access control, malformed response, legitimate empty result, source or schema drift, rate limit, cancellation, operator abort, partial result, and retention failure. Retries are bounded and evidence-bearing. Access-control outcomes are terminal and prohibit bypass.

## Operational boundary

Production recurrence and concurrent live integration remain prohibited until persisted attempt uniqueness, operational rate and concurrency controls, cancellation/checkpoint semantics, and adversarial concurrency tests exist.

## Consequences

A request path without complete policy is uncertifiable. Silent fallback clients, unrestricted redirects, unbounded response reads, and broad exception swallowing are prohibited.
