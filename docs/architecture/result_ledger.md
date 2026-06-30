# Result Ledger

The result ledger records the final business result for a reviewed lead workflow.

## Current implementation

The current implementation includes:

- `ResultLedgerStatus`
- `ResultLedgerRecord`
- `ResultShareRecord`
- result ledger service helper
- calculated share value
- model and service tests

## Statuses

The current result statuses are:

- `open`
- `won`
- `lost`
- `no_fit`
- `unknown`

## Share calculation

A share record stores:

- workflow ID
- gross value
- share rate
- calculated share value

The current model requires `share_value` to equal `gross_value * share_rate`, rounded to cents.

## Known limitation

The current service can create a `won` ledger row with a gross value and a limitation when the share rate is missing. This preserves uncertainty but does not yet distinguish a complete won result from a pending-share result.

## Required hardening

A future cleanup PR should decide one of these policies:

1. add an explicit pending-share status, or
2. require every won result to include both gross value and share record.

Do not silently change this rule without business review.
