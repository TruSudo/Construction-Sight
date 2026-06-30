# Audit Package

The audit package is a report-only layer used after source readiness checks.

It keeps a compact review record for each source target:

- original URL
- final URL when checked
- HTTP status when available
- redirect class
- registry state
- adapter state
- readiness state
- reasons
- limitations
- next action

The package does not edit registry files. It does not replace manual source verification. It does not create verified source coverage. It is intended to support operator review before any later registry update workflow is designed.

Operator command:

```text
constructionsight-audit-package build data/source_registry.seed.json
constructionsight-audit-package build data/source_registry.seed.json --json-output
constructionsight-audit-package build data/source_registry.seed.json --check-http
constructionsight-audit-package build data/source_registry.seed.json --check-http --json-output
```

## Current observed HTTP audit-package outcome

The current seed registry has four sources. A `--check-http` audit-package run produced these report-only classifications:

| Source | Redirect classification | Recommendation |
|---|---|---|
| CEQAnet State Clearinghouse | `cross_host_redirect` | `keep_unverified_reachable` |
| CSLB Public License Search | `no_redirect` | `keep_unverified_reachable` |
| San Bernardino County EZOP | `same_host_redirect` | `keep_unverified_reachable` |
| Riverside County PLUS Online | `downgraded_to_http` | `keep_unverified_reachable` |

These results mean the URLs were reachable in that run, but all four source records remain unverified. Reachability and redirect evidence are review inputs only. They are not source promotion and not live source coverage.
