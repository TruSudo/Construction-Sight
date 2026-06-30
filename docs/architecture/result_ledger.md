# Result Ledger

The result ledger records the business result for a reviewed lead workflow.

## Current implementation

The current implementation includes:

- `ResultLedgerStatus`
- `ResultShareStatus`
- `ResultLedgerRecord`
- `ResultShareRecord`
- result ledger service helper
- calculated share value
- explicit pending-share states
- model, service, and storage tests

## Result statuses

The current result statuses are:

- `open`
- `won`
- `lost`
- `no_fit`
- `unknown`

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

The model requires `share_value` to equal `gross_value * share_rate`, rounded to cents.

## Business rule

A `won` ledger may be incomplete, but it must be explicit. It may not silently look complete when share math is pending.

```text
won + no gross value -> pending_gross_value
won + gross value + no share rate -> pending_share_rate
won + gross value + share rate -> calculated share record
non-won -> not_applicable
```

This preserves the uncertainty required for audit replay while keeping pending-share work queryable.
