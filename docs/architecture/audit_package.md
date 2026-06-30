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

The package does not edit registry files. It is intended to support operator review before any later registry update workflow is designed.

Operator command:

```text
constructionsight-audit-package build data/source_registry.seed.json
constructionsight-audit-package build data/source_registry.seed.json --json-output
constructionsight-audit-package build data/source_registry.seed.json --check-http
```
