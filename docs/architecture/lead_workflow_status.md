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

## Known limitation

The current transition helper appends status events but does not yet enforce a transition matrix. That means the model can preserve a status history, but it does not yet prevent every invalid state jump.

## Required hardening

A future cleanup PR must add transition rules for at least:

```text
hold -> monitor/review
monitor -> review/ready/hold
review -> ready/hold/monitor
ready -> active/paused/closed_no_fit
active -> paused/closed_success/closed_no_fit
paused -> active/closed_no_fit
closed_* -> immutable unless explicit override
```

## Forward requirement

No external workflow action should be driven from a lead workflow record unless the current status and latest event are consistent and any duplicate/review limitations have been resolved or explicitly accepted.
