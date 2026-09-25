# Parcel ArcGIS Live-Rehearsal Authorization

The live-rehearsal authorization layer separates capability from authority. ConstructionSight may contain a tested HTTP adapter, complete-rehearsal executor, and portable proof bundle without having permission to execute either official county source. A live rehearsal becomes eligible only after a separate, exact-plan, expiring authorization is issued and passes offline preflight.

## Authorization contract

`ParcelArcGISBulkRehearsalAuthorization` binds:

- the exact capability snapshot, verification profile, and digest-bound rehearsal plan;
- the source key, county, HTTPS layer `/query` endpoint, and object-ID field;
- page size, checkpoint position, resumed-segment retry page, and maximum attempts;
- a unique 64-hex execution nonce;
- the issuer, authorization reason, issuance time, not-before time, and expiration time;
- exactly one authorized execution and exactly two count requests;
- GET-only, geometry-disabled access;
- mandatory exact-response retention, durable checkpoint proof, portable proof-bundle creation, and independent offline verification; and
- explicit operator authorization for one complete read-only rehearsal.

The authorization window may not exceed 24 hours. Its identity is a SHA-256 digest over every authority-significant field. Any scope, plan, timing, nonce, issuer, reason, retention, or authority change invalidates the stored identity.

## Authority exclusions

The authorization model fixes the following fields to false:

- credential use;
- access-control bypass;
- parcel import;
- source-profile promotion;
- recurring execution; and
- production bulk-run authority.

Issuing one rehearsal authorization therefore cannot silently authorize downstream ingestion, scheduling, promotion, or production collection.

## Offline preflight

`preflight_arcgis_bulk_rehearsal_authorization` requires:

- the exact expected authorization identity;
- the same capability snapshot and digest-bound plan;
- a timezone-aware check within the not-before and expiration window;
- an authorization identity not present in the caller-supplied consumed-ID collection; and
- complete agreement on source, county, endpoint, object-ID field, page, checkpoint, retry, and attempt scope.

A successful `ParcelArcGISBulkRehearsalPreflight` is time-bound to the authorization expiration. It confirms eligibility for exactly one live rehearsal but preserves false authority for import, promotion, recurring execution, and production bulk collection.

## Single-use boundary

The current service accepts a caller-supplied collection of consumed authorization identities and rejects reuse. No operational authorization-consumption ledger is implemented or committed in this phase. Before any live execution command is added, a later phase must define durable, append-only consumption evidence that atomically binds:

- the authorization and preflight identities;
- execution start and completion times;
- the resulting manifest and portable proof-bundle identities;
- independent verification identity;
- success, terminal failure, or abandoned status; and
- the rule that an attempted authorization cannot be silently reused.

Until that durable consumption boundary exists, the authorization and preflight services remain offline governance primitives rather than an executable live command.

## Current repository state

The repository contains the authorization schema, guarded builder, offline preflight service, and deterministic fail-closed tests. It contains no issued San Bernardino or Riverside authorization artifact, no live county execution command, no network request from this phase, and no consumption ledger.

Both official county sources remain `bounded_query_verified`, not `bulk_rehearsal_verified`. A future live-proof phase must separately issue an authorization, pass preflight, consume it exactly once through an append-only ledger, execute the governed rehearsal, save the portable bundle, and independently verify the saved proof before any profile-promotion review.
