# Bid Pricing Preview

ConstructionSight Bid Studio can build an internal manual pricing preview only after a content-bound Bid Request Evidence packet has been validated against current persisted workflow state.

## Current implementation

The pricing preview includes:

- the exact `request_evidence_id`;
- exact workflow, review package and candidate identity inherited from the request evidence;
- an explicit three-letter currency code;
- versioned pricing semantics: `manual_line_amounts/v1`;
- 1 to 100 operator-entered pricing lines;
- description and pricing basis for every line;
- exact integer currency minor units for every amount;
- exact subtotal as the sum of normalized minor units;
- assumptions, exclusions and validity language;
- content-bound `pricing_preview_id`;
- same-origin read-only operator HTTP preview;
- a chained Bid Studio form after request evidence validation.

## Money doctrine

ConstructionSight does not use browser or binary floating-point arithmetic to establish bid amounts.

Each operator-entered decimal amount is normalized by the existing governed `money_minor_units()` routine:

- scale: two decimal places;
- finite values only;
- nonnegative values only;
- more than two decimal places are rejected;
- subtotal is integer addition over currency minor units.

The browser may format returned integer minor units for display, but it does not calculate the authoritative subtotal.

## Revalidation

Pricing does not trust a detached request packet. Before normalizing any line amount, the service:

1. validates the supplied Bid Request Evidence content identity;
2. reloads the exact persisted workflow;
3. verifies expected current workflow status;
4. rechecks unresolved workflow limitations;
5. rechecks durable duplicate state;
6. reloads and verifies the exact review package;
7. reconstructs the request-evidence packet from current state;
8. requires the reconstructed `request_evidence_id` to equal the supplied identity.

A stale, forged, or detached request packet therefore cannot be used as the basis for pricing preview.

## Authority boundary

Every pricing preview is fixed to:

- `requires_commercial_approval = true`
- `commercial_terms_authorized = false`
- `customer_facing_bid_authorized = false`
- `bid_submission_authorized = false`

The current capability does not approve rates, infer market prices, create legally binding terms, persist an approved proposal, communicate with a customer, or submit a bid.

## Next gate

A future proposal-draft layer may bind request evidence, exact pricing identity, requested scope, assumptions, exclusions and validity language into an internal customer-facing-format draft. That draft must still remain non-authorized until a separate scope-bound commercial approval is issued and consumed.
