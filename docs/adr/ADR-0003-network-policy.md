# ADR-0003: Complete policy for every network path

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

Every production network client must live in an approved transport module and have exactly one complete entry in `governance/network_contract.toml`. Application and domain code use explicit transport interfaces rather than importing clients directly.

Every request is represented by one strict canonical wire URL before authorization. Nonempty query scope is executable, not prose: the immutable operation policy must contain the complete canonical request identity, and the shared engine transmits the same validated URL object. Ambiguous encoded paths, user information, fragments, dot segments, backslashes, noncanonical percent encodings, and client-normalized representations are rejected before any request.

Policies distinguish transport failure, timeout, retryable and terminal status, access control, malformed response, legitimate empty result, source or schema drift, rate limit, cancellation, operator abort, partial result, and retention failure. Retries are bounded and evidence-bearing. Access-control outcomes are terminal and prohibit bypass.

## Operational boundary

Production recurrence and concurrent live integration remain prohibited until persisted attempt uniqueness, operational rate and concurrency controls, cancellation/checkpoint semantics, and adversarial concurrency tests exist.

## Consequences

A request path without complete policy is uncertifiable. Silent fallback clients, unrestricted redirects, unbounded response reads, broad exception swallowing, caller-injected base URLs, and alternate test/compatibility transports are prohibited. Deterministic clients must enter through the same bounded engine as the default client.
