# Lead Workflow Status

Lead workflow status is the audit trail after lead review and dedupe.

## Current implementation

The current implementation includes:

- `LeadWorkflowStatus`
- `LeadWorkflowEvent`
- `LeadWorkflowRecord`
- workflow creation from a lead review package
- optional dedupe-result influence
- deterministic status events
- append-only status transition helper
- matrix-constrained status rules
- immutable final statuses
- model and service tests

## Statuses

The current status enum includes:

- `hold`
- `monitor`
- `review`
- `ready`
- `active`
- `paused`
- `closed_success`
- `closed_no_fit`

## Transition matrix

Workflow status changes are constrained by this matrix:

```text
hold -> monitor/review
monitor -> review/ready/hold
review -> ready/hold/monitor
ready -> active/paused/closed_no_fit
active -> paused/closed_success/closed_no_fit
paused -> active/closed_no_fit
closed_success -> no outgoing status
closed_no_fit -> no outgoing status
```

A status move outside the matrix raises an error before an event is appended. Final statuses do not move to another status unless a later explicit override feature is added with separate doctrine and tests.

## Forward requirement

No external workflow action should be driven from a lead workflow record unless the current status and latest event are consistent and any duplicate/review limitations have been resolved or explicitly accepted.
