# Network and resilience governance

All direct and indirect production network clients are classified in `governance/network_contract.toml`. The architecture certifier rejects an import of HTTP, socket, browser, or external-client capability outside an approved transport module and rejects an approved module without a complete policy.

Each policy binds the applicable method, hosts, path prefixes, query and body scope, connect/read/write/pool timeout, response-size ceiling, redirect behavior, accepted media types and encodings, retryable and terminal failures, attempt count, backoff, jitter, idempotency, rate and concurrency limits, circuit-breaker or explicit nonapplicability, bulkhead, cancellation, partial-result behavior, evidence retention, telemetry, credentials, robots/terms review, access-control posture, and no-bypass authority.

The shared bounded engine accepts only an already-canonical ASCII HTTP(S) wire identity. It rejects user information, fragments, explicit ports, backslashes, dot segments, ambiguous encoded path separators, noncanonical percent encodings, and any representation that `httpx.URL` would change. The engine validates and transmits the same `httpx.URL` object. A request with a query cannot execute unless its complete canonical URL appears in the immutable operation policy's `allowed_request_urls`; key, value, order, host, path, or encoding drift therefore fails before transport.

CEQAnet listing plans have one hard-coded reviewed search action. The live executor recomputes canonical planner output before every effect and routes both ordinary and injected deterministic clients through the common engine. CEQAnet CSV execution uses the same path; there is no compatibility branch with separate redirect or body-reading behavior.

## Failure distinctions

A transport failure is not an empty result. A timeout is not an access-control denial. A retryable status is not a terminal status. A malformed response is not source drift. Cancellation, operator abort, partial completion, and retention failure remain independently represented. Code must not collapse these outcomes merely to make a caller receive a Boolean or an empty list.

Retries are bounded, policy-declared, idempotent, and evidence-bearing. Access-control outcomes are terminal and may not trigger alternate clients, credentials, endpoints, browser automation, or other bypass behavior.

## Operational boundary

The present implementation permits only bounded manually initiated operations already represented by exact plans and operation-specific authorization. Production recurrence and concurrent live integration are prohibited. Their entry conditions include persisted attempt uniqueness, rate and concurrency enforcement, cancellation and checkpoint doctrine, circuit/bulkhead behavior where applicable, operational telemetry, and adversarial concurrency testing.

## Evidence retention

A request cannot be reported as successful when required response or audit evidence could not be retained. Exact request identity, final URL, status, relevant headers, bounded response bytes or digest, retry chronology, classification, and limitation evidence must survive according to the operation policy.
