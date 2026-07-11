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
- append-only persistence enforcement
- model, service, and storage tests

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

## Share states

The current share states are:

- `not_applicable` — non-won result or result where share does not apply
- `pending_gross_value` — won result exists but gross contract value is not known yet
- `pending_share_rate` — won result has gross value but share rate is not known yet
- `calculated` — won result has a valid calculated share record

## Share calculation

A calculated share record stores:

- workflow ID
- gross value
- share rate
- calculated share value

The model requires `share_value` to equal `gross_value * share_rate`, rounded to cents. Share identity is scoped to the ledger revision that produced it, and persisted share payloads are immutable.

## Business rules

A `won` ledger may be incomplete, but it must be explicit. It may not silently look complete when share math is pending.

```text
won + no gross value -> pending_gross_value
won + gross value + no share rate -> pending_share_rate
won + gross value + share rate -> calculated share record
non-won -> not_applicable
```

Uncertainty remains visible in each revision. Corrections create a new revision rather than overwriting uncertainty, reasons, limitations, dates, values, or prior outcome states.