# ADR-0008: Bind defect closure to reviewed Git history

- Status: Accepted
- Date: 2026-08-21
- Revised: 2026-09-25
- Owners: ConstructionSight maintainers

## Context

ConstructionSight retains every defect permanently as audit history, but an implementation
correction must be able to move a defect from the active ledger to the resolved ledger.
The earlier closure model made that transition depend on a cumulative assurance artifact
that itself could not pass while any active defect remained. It also required all reviewed
active defects to close in one finalization transaction. That created a circular closure
condition and prevented independently corrected defects from ever leaving the active set.

The defect ledger is not the assurance report. It records whether a specific historical
root cause is still unresolved. Final Native Maximum Assurance remains a separate
whole-tree release/certification decision.

## Decision

Defect closure is incremental and evidence-bound.

A defect may move from `governance/active_defects.toml` to
`governance/resolved_defects.toml` only when:

- its original ID, severity, area, root cause, discovery commit, and required resolution
  are preserved exactly from a named `last_active_commit`;
- the correction is bound to a real `resolution_commit` in the current Git history;
- the exact Git tree for that resolution commit is retained as `resolution_tree`;
- the resolution commit is an ancestor of the last-active commit, proving the correction
  existed while the defect was still formally active;
- safe existing evidence paths and regression-test paths are retained;
- a safe defect-specific closure evidence document is retained under
  `docs/assurance/defect_closures/`;
- the defect is absent from the active ledger and appears exactly once in the resolved
  ledger; and
- canonical CI continues to treat every remaining active defect as a certification
  blocker.

The resolved-defect ledger therefore uses schema
`constructionsight.resolved-defects/v2`.

Whole-tree Native Maximum Assurance does not authorize individual ledger moves and is
not required before an individually corrected defect can be closed. Instead, canonical
exact-head CI validates the incrementally updated ledgers and the regression suite.
Native Maximum Assurance remains required for a final certified zero-active-defect tree.

If later changes reintroduce a previously resolved failure mode, the historical resolved
record is never deleted or rewritten. The regression failure blocks CI and a new active
defect record is opened if the regression represents a new tracked defect state.

## Consequences

ConstructionSight can now reduce the active count one proven defect at a time without
erasing history or weakening certification. Resolved defects remain permanent audit
records. Active count can legitimately reach zero, at which point final whole-tree
assurance and owner acceptance certify the integrated candidate.
