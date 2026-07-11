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
- a deterministic SHA-256 digest of the complete ordered registry snapshot
- a deterministic SHA-256 approval digest covering the registry digest and all approval-significant plan-row content

Generation timestamps are excluded from the approval digest so equivalent plans remain reproducible. Registry order is included in the registry digest because the registry file is an ordered operational artifact.

Operator commands:

```text
constructionsight-source-plan plan data/source_registry.seed.json
constructionsight-source-plan plan data/source_registry.seed.json --json-output
constructionsight-source-plan plan data/source_registry.seed.json --output data/source_registry_update_plan.json
constructionsight-source-plan plan data/source_registry.seed.json --observations-path observations.json
```

The plan command never edits registry data. A plan output may not alias the registry or observation input path. Existing plan output files are refused unless `--overwrite` is supplied, and plan output uses same-directory atomic replacement.

## Controlled apply boundary

The apply command is intentionally narrow. It rejects the operation unless all of the following are true:

1. The operator supplies `--apply`.
2. The supplied approval digest exactly matches the reviewed plan digest.
3. Recomputed plan content still matches that digest.
4. The complete current registry content and order match the registry snapshot digest embedded in the plan.
5. Plan source counts, update counts, and action counts match the plan rows.
6. Every planned source still matches its original payload and current status.
7. Every applied status change has at least one evidence reference.
8. The planned action and proposed status agree.
9. The proposed payload changes only `verification_status`.
10. The proposed payload preserves the canonical source identity.
11. A currently verified source is not downgraded through the promotion workflow.
12. The entire plan validates before any registry output is written.

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

Apply inputs and outputs must resolve to distinct paths, except that `--in-place` intentionally designates the registry input as the final target. This prevents a nominal separate-output operation from overwriting the live registry without a backup and prevents audit or output paths from destroying the approved plan.

Each individual file replacement is atomic. For in-place apply, the backup is written first, the audit report second, and the registry target last. For separate-output apply, the audit report is written before the updated registry output. This commit order ensures that a changed registry target is never created before its required audit artifact and, for in-place operation, its backup artifact.

Existing output, audit, or backup files are refused unless `--overwrite` is supplied. The audit report preserves the plan digest, original and updated registry digests, row-level reasons, limitations, evidence references, and applied statuses.

A registry verification status is not a claim of production-grade recurring integration. This workflow does not make any current seed source verified, does not implement live adapters, and does not establish production coverage.
