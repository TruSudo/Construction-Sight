# Outreach Preview

ConstructionSight outreach preview is a governed, no-send operator boundary between a reviewed lead workflow and any future external communication capability.

## Current implementation

The current implementation includes:

- `OutreachContactReference`
- `OutreachPreview`
- a content-bound preview identity
- persisted workflow and review-package integrity checks
- durable duplicate-state revalidation
- explicit business-contact provenance
- a required operator contact-review basis
- `constructionsight-leads outreach-preview`
- service and CLI regression coverage

## Eligibility

A preview may be built only when all of these are true:

1. the exact persisted workflow exists;
2. the operator supplies the expected current workflow status;
3. the workflow is `ready` or `active`;
4. the workflow has no unresolved limitations;
5. persisted duplicate suppression has no unresolved duplicate or review-needed result;
6. the exact persisted review package matches the workflow;
7. the review package is `ready` and has no unresolved limitations;
8. the operator records a nonblank review basis for treating the supplied destination as a business contact path.

Early opportunity scoring, a green display state, or a contact hint alone cannot satisfy this gate.

## Contact provenance

The preview requires:

- contact channel;
- destination;
- business role;
- source name;
- source reference;
- a nonblank operator contact-review basis.

The preview service does not harvest contacts, infer consent, or determine that a communication is legally permissible to send. Contact acquisition and future delivery compliance remain separate governed concerns.

## Effect boundary

Every preview is fixed to:

- `requires_human_approval = true`
- `external_send_authorized = false`
- `send_executed = false`
- `bid_authorized = false`

There is no SMTP, messaging, procurement submission, web-form submission, or other external delivery transport in this capability.

## Identity and replay

`preview_id` is derived from the exact semantic preview content while excluding receipt time. Rebuilding the same reviewed preview produces the same content identity; changing the workflow, contact provenance, destination, subject, body, or authority flags changes the identity.

## Future work

Future outreach delivery, if implemented, must be a separate protected effect with:

- explicit operator approval;
- exact preview identity binding;
- current-state and duplicate revalidation;
- suppression/opt-out checks where applicable;
- channel-specific compliance checks;
- delivery receipt/audit history;
- failure and retry governance that cannot silently double-send.

Bid generation and bid submission remain separate from outreach preview.
