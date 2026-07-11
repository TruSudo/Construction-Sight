# Source Registry Update Plan and Controlled Apply

The source registry update plan is built after source status, readiness, audit-package, checklist, observation, and source-promotion analysis. Planning remains dry-run-first. A separate controlled apply command may write only an explicitly approved verification-status change.

## Plan artifact

The plan preserves:

- source key and name
- current verification status
- proposed verification status, if any
- planned action
- original source payload
- proposed source payload, when an update is proposed
- reasons
- limitations
- evidence references
- next action
- a deterministic SHA-256 plan digest that excludes generation timestamps

Operator commands:

```text
constructionsight-source-plan plan data/source_registry.seed.json
constructionsight-source-plan plan data/source_registry.seed.json --json-output
constructionsight-source-plan plan data/source_registry.seed.json --output data/source_registry_update_plan.json
constructionsight-source-plan plan data/source_registry.seed.json --observations-path observations.json
```

The plan command never edits registry data.

## Controlled apply boundary

The apply command is intentionally narrow. It rejects the operation unless all of the following are true:

1. The operator supplies `--apply`.
2. The supplied approval digest exactly matches the reviewed plan digest.
3. Recomputed plan content still matches that digest.
4. Every planned source still matches its original payload and current status.
5. Every applied status change has at least one evidence reference.
6. The planned action and proposed status agree.
7. The proposed payload changes only `verification_status`.
8. The proposed payload preserves the canonical source identity.
9. A currently verified source is not downgraded through the promotion workflow.
10. The entire plan validates before any registry output is written.

Separate-output example:

```text
constructionsight-source-plan apply \
  data/source_registry.seed.json \
  data/source_registry_update_plan.json \
  --approved-plan-digest <reviewed-sha256> \
  --output data/source_registry.updated.json \
  --audit-output data/source_registry_apply_audit.json \
  --apply
```

In-place example:

```text
constructionsight-source-plan apply \
  data/source_registry.seed.json \
  data/source_registry_update_plan.json \
  --approved-plan-digest <reviewed-sha256> \
  --in-place \
  --backup-output data/source_registry.seed.backup.json \
  --audit-output data/source_registry_apply_audit.json \
  --apply
```

Each file replacement is atomic. Existing output, audit, or backup files are refused unless `--overwrite` is supplied. The audit report preserves the plan digest, original and updated registry digests, row-level reasons, limitations, evidence references, and applied statuses.

A registry verification status is not a claim of production-grade recurring integration. This workflow does not make any current seed source verified, does not implement live adapters, and does not establish production coverage.
