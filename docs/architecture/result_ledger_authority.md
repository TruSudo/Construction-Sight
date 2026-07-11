# Result Ledger Authority

## Purpose

ConstructionSight separates immutable outcome evidence from the one current authoritative outcome for a lead workflow.

A result correction must never overwrite the earlier ledger row. It must create a new immutable ledger record, atomically move the workflow's authority pointer, and append an authority event explaining the change.

## Record layers

### Immutable result ledger

`ResultLedgerRecord` represents one complete outcome assertion. Its identifier is content-addressed over approval-significant fields:

- workflow identifier;
- review-package identifier;
- outcome status;
- decision date;
- gross value;
- share rate when applicable;
- canonical sorted reasons.

The observation timestamp is deliberately excluded from identity. Rebuilding the same semantic outcome later produces the same ledger ID and is treated as idempotent replay. Changing an outcome-significant field produces a different ledger ID.

Persisted ledger and share rows are immutable. A repeated ID with different semantic content is an identity collision and fails. Existing rows are not updated in place.

### Current authority pointer

`ResultLedgerAuthorityRecord` identifies the one current authoritative ledger for a workflow. It stores:

- deterministic authority ID;
- workflow ID;
- current ledger ID;
- monotonically increasing revision;
- update timestamp.

There is one authority row per workflow.

### Append-only authority events

`ResultLedgerAuthorityEvent` records every authority establishment or correction:

- previous ledger ID, or none for the initial authority;
- current ledger ID;
- workflow revision;
- required operator reason;
- creation timestamp.

The event table enforces one event per workflow revision. Event identity excludes observation time and includes workflow, revision, previous/current ledger IDs, and reason.

## Initial authority

The first authoritative result requires:

- no existing authority pointer;
- no expected-current ledger value;
- a canonical result ledger whose workflow and package match the reviewed workflow;
- a result status compatible with workflow status;
- a nonblank reason.

The initial authority has revision 1 and an event with no previous ledger ID.

## Correction

A correction requires:

- an existing authority pointer;
- the exact ledger ID the operator reviewed;
- a different canonical replacement ledger;
- a nonblank correction reason.

The service increments the revision, preserves the previous immutable ledger, appends an authority event, and moves the current pointer.

A correction to the already authoritative ledger is a no-op and fails.

## Stale-state and concurrency protection

The operator expectation is checked twice:

1. the service compares the supplied expected ledger ID to the loaded current authority;
2. persistence performs an atomic compare-and-swap over workflow ID, authority ID, current ledger ID, and revision.

If another transaction changes authority after operator review, the compare-and-swap affects no row and the correction fails. The transaction does not silently overwrite the concurrent result.

Ledger insertion, pointer creation or replacement, and authority-event insertion execute in a nested transaction. Any error rolls back the complete authority change.

## Workflow and outcome compatibility

Authoritative results are constrained by workflow state:

| Workflow status | Allowed authoritative result |
|---|---|
| `closed_success` | `won` |
| `closed_no_fit` | `lost` or `no_fit` |
| Any non-final status | `open` or `unknown` |

This prevents a non-final workflow from being declared won or lost and prevents a successful closed workflow from carrying a contradictory negative result.

## Integrity checks

Before authority is applied or loaded, ConstructionSight verifies:

- canonical ledger content identity;
- canonical share identity when a calculated share exists;
- canonical sorted reasons;
- workflow and package agreement;
- workflow/outcome compatibility;
- indexed database columns against preserved JSON payloads;
- current authoritative ledger existence and workflow ownership;
- strictly increasing revisions;
- unique workflow/revision authority events.

Malformed payloads and indexed/payload drift fail explicitly.

## Existing historical rows

Ledger rows created before content-addressed identity remain readable history. They are not eligible to become authoritative unless rebuilt through the canonical result-ledger service so their IDs and derived share state can be verified.

No destructive migration or silent ID rewrite occurs in this phase.

## Operator boundary

This phase establishes the domain service and persistence foundation. It does not yet expose a result-mutation CLI.

A future operator command must call `apply_authoritative_result_ledger` and require:

- explicit apply authorization;
- exact expected-current ledger ID for corrections;
- a nonblank reason;
- canonical workflow and result inputs;
- machine-readable audit output.

Ledger and authority history must remain inspectable through the lead operator surface.
