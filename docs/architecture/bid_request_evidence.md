# Bid Request Evidence

ConstructionSight Bid Studio now has a request-evidence gate that proves a prospect-requested bid exists before any pricing or proposal work may begin.

## Current implementation

The current implementation includes:

- `BidRequestEvidence` with content-bound identity;
- exact persisted workflow and review-package integrity checks;
- durable duplicate-state revalidation;
- explicit requester business identity and role;
- explicit request channel, source name and source reference;
- a required operator review basis;
- an offset-aware observed request timestamp;
- retained request text and requested security scope;
- a read-only same-origin `/api/bid-request-evidence` operator endpoint;
- a Bid Studio Command Center form that validates request evidence only;
- service and HTTP regression coverage.

## Eligibility

A request-evidence packet may be built only when:

1. the exact persisted workflow exists;
2. the operator supplies the expected current workflow status;
3. the workflow is `ready` or `active`;
4. the workflow has no unresolved limitations;
5. durable duplicate suppression has no unresolved duplicate or review-needed result;
6. the exact persisted review package matches the workflow;
7. the review package is `ready` and has no unresolved limitations;
8. the prospect request has a business requester, role, source, reference and review basis;
9. the observed request timestamp is timezone-aware;
10. request text and requested security scope are nonblank.

Lead readiness, a green UI state, an outreach preview, or an operator desire to price work cannot satisfy this gate by themselves.

## Authority boundary

Every `BidRequestEvidence` packet is fixed to:

- `requires_commercial_approval = true`
- `pricing_authorized = false`
- `bid_preparation_authorized = false`
- `bid_submission_authorized = false`

The current endpoint is read-only. It does not persist the request packet, calculate labor or equipment prices, create proposal terms, generate a customer-facing bid, authorize commercial terms, or submit anything externally.

## Identity

`request_evidence_id` is a SHA-256 content identity over the semantic request evidence while excluding receipt time and the stored ID itself. Changing the workflow, requester, source, review basis, observed request time, request text, scope, evidence notes, or authority flags changes the identity.

## Next gate

Before Bid Studio can prepare pricing or a proposal, ConstructionSight must add a separate governed commercial-approval layer that binds:

- the exact request-evidence identity;
- a persisted or otherwise integrity-protected request record;
- the exact customer-requested scope;
- pricing inputs and versioned pricing rules;
- exclusions, assumptions and validity period;
- the authorized commercial approver and scope;
- stale-state and duplicate revalidation;
- a content-bound proposal identity;
- explicit denial of external submission until a separately authorized send/submit effect exists.

Request evidence is therefore a prerequisite for Bid Studio, not bid authority.
