# Source Promotion Plan

The source promotion plan is a dry-run report built after source status, readiness, audit-package, checklist, and optional operator observations.

It does not edit `data/source_registry.seed.json`. It does not create verified source coverage. It does not add live source integration.

The plan can recommend:

- `keep_unverified`
- `mark_blocked_candidate`
- `mark_failed_candidate`
- `mark_partial_candidate`
- `verified_candidate_review`

A candidate action is still only a review recommendation. A future registry update workflow must be explicit, dry-run-first, and separately tested before any source registry data changes.

Operator command:

```text
constructionsight-source-promotion plan data/source_registry.seed.json
constructionsight-source-promotion plan data/source_registry.seed.json --json-output
constructionsight-source-promotion plan data/source_registry.seed.json --check-http
constructionsight-source-promotion plan data/source_registry.seed.json --observations-path observations.json
```

The plan requires manual observation evidence before it recommends anything stronger than `keep_unverified` for normal reachable sources.
