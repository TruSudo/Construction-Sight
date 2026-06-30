# Source Readiness Workflow

Source readiness is a conservative operator workflow for inspecting source registry records without mutating them or claiming production live coverage.

## Core rule

A source-readiness report is evidence for review. It is not a registry update and not a live-source coverage claim.

The workflow preserves:

- source key
- source name
- platform family
- public URL
- lawful-access boundary
- source registry verification status
- adapter implementation status
- HTTP reachability result when checked
- reason
- limitations
- next action
- timestamp
- JSON output

## Readiness statuses

The report can emit these statuses:

- `seed_only` — source is only a registry seed or has not been checked by this workflow
- `reachable` — public URL was reachable, but source verification is still not complete
- `blocked` — registry state or HTTP response indicates blocked/unauthorized public access
- `failed` — prior verification or HTTP reachability failed
- `partial` — some readiness exists, but source and adapter maturity do not support verified usable coverage
- `verified_candidate` — source and adapter state are strong enough for explicit human review before any registry update

## HTTP behavior

HTTP checking is explicit. The CLI does not mutate source registry records. It can produce report-only evidence with:

```text
constructionsight-source-readiness check data/source_registry.seed.json
constructionsight-source-readiness check data/source_registry.seed.json --json-output
constructionsight-source-readiness check data/source_registry.seed.json --check-http
```

The HTTP check is intentionally lightweight public reachability only. It does not bypass authentication, captchas, rate limits, access controls, paywalls, robots restrictions, or terms-of-service limits.

## Relationship to source status

`constructionsight-source-status` answers: "What does the registry and adapter metadata currently claim?"

`constructionsight-source-readiness` answers: "What conservative readiness evidence can an operator review before any future registry status change?"

Neither command changes source verification state.
