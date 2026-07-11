# Result Ledger

The result ledger records the business result for a reviewed lead workflow as an append-only authoritative history.

## Current implementation

The current implementation includes:

- `ResultLedgerStatus`
- `ResultShareStatus`
- `ResultLedgerRecord`
- `ResultShareRecord`
- immutable root and superseding revisions
- contiguous revision and predecessor validation
- calculated share value
- explicit pending-share states
- append-only ledger and share persistence
- a unique per-workflow authority head for serialized compare-and-swap writes
- append-only authority audit events
- governed `constructionsight-results` inspection and write commands
- model, service, storage, CLI, and concurrency-boundary tests

## Result statuses

The current result statuses are:

- `open`
- `won`
- `lost`
- `no_fit`
- `unknown`

## Authority and correction doctrine

One workflow has one linear result history. Revision one is the root. Every later revision must:

- increment the prior revision by exactly one;
- identify the immediately superseded ledger ID;
- include a nonblank correction reason;
- preserve the same workflow and package identity; and
- be appended without changing or deleting the prior payload.

The authoritative result is the validated tip of that chain. Branches, revision gaps, duplicate ledger IDs, cross-workflow histories, self-supersession, and in-place payload rewrites are rejected. This permits corrections without erasing what was previously recorded or allowing contradictory outcomes to appear concurrently authoritative.

## Serialized authority head

`result_authority_heads` contains one mutable row per workflow. It is a concurrency control, not the business evidence record.

The head stores the currently reviewed ledger ID and revision. A correction may move the head only through an atomic compare-and-swap that matches both values. If another writer changes the head after review, the correction fails as stale.

Immutable ledger revisions remain the result evidence. `result_authority_events` separately records each governed initial selection and correction. A transaction must write the new immutable ledger revision, move or establish the head, and append the authority event together; partial authority changes are rolled back.

Validated histories created before the authority-head table remain readable. The first later correction may bootstrap a head at the already validated tip without rewriting earlier ledger rows. Historical revisions do not acquire fabricated authority events retroactively.

## Operator commands

`constructionsight-results` exposes:

- `current WORKFLOW_ID` — validate and show the authoritative history tip;
- `history WORKFLOW_ID` — show every immutable revision and available authority event; and
- `record WORKFLOW_ID STATUS` — create the root result or append one correction.

`record` requires:

- explicit `--apply` authorization;
- `--expected-current-ledger-id` containing the exact reviewed tip, or the literal `none` for a first result;
- a nonblank `--reason` for the authority audit event;
- a persisted workflow whose indexed fields agree with its full payload; and
- a result payload accepted by the canonical ledger builder.

The command rejects stale expectations, no-op corrections, malformed or drifted persisted payloads, non-won monetary inputs, invalid date text, and partial writes.

## Share states

The current share states are:

- `not_applicable` — non-won result or result where share does not apply
- `pending_gross_value` — won result exists but gross contract value is not known yet
- `pending_share_rate` — won result has gross value but share rate is not known yet
- `calculated` — won result has a valid calculated share record

## Share calculation and numeric policy

A calculated share record stores:

- workflow ID
- gross value
- share rate
- calculated share value

The model requires `share_value` to equal `gross_value * share_rate`, rounded to cents. Share identity is scoped to the ledger revision that produced it, and persisted share payloads are immutable.

New canonical writes require gross and share currency values at cent precision and share rates at no more than six decimal places. Share identity preserves at least the historical four-decimal encoding and extends through the accepted input precision. Older persisted result payloads remain readable; stricter numeric policy applies to newly constructed revisions rather than silently invalidating history.

## Business rules

A `won` ledger may be incomplete, but it must be explicit. It may not silently look complete when share math is pending.

```text
won + no gross value -> pending_gross_value
won + gross value + no share rate -> pending_share_rate
won + gross value + share rate -> calculated share record
non-won -> not_applicable
```

New canonical writes reject monetary fields on non-won results and reject a share rate when gross value is absent. Uncertainty remains visible in each revision. Corrections create a new revision rather than overwriting uncertainty, reasons, limitations, dates, values, or prior outcome states.
