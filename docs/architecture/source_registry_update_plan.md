# Source Registry Update Plan

The source registry update plan is a dry-run artifact built after source status, readiness, audit-package, checklist, observation, and source-promotion plan output.

It does not edit `data/source_registry.seed.json`. It only shows what registry status change would be proposed if a future explicit apply workflow existed.

The plan preserves:

- source key and name
- current verification status
- proposed verification status, if any
- planned action
- original source payload
- proposed source payload, when an update is proposed
- reasons
- limitations
- next action

Operator command:

```text
constructionsight-source-plan plan data/source_registry.seed.json
constructionsight-source-plan plan data/source_registry.seed.json --json-output
constructionsight-source-plan plan data/source_registry.seed.json --output data/source_registry_update_plan.json
constructionsight-source-plan plan data/source_registry.seed.json --observations-path observations.json
```

This is still not a registry mutation workflow. A future apply workflow must be separate, explicit, tested, and dry-run-first.
