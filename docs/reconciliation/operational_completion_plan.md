# ConstructionSight operational completion plan

Status: active development plan for draft PR #201; not a production release or merger authorization.
Scope: San Bernardino and Riverside Counties first. Preserve approved charcoal/amber Command Center and the existing public-access and evidence-first policies.

## Release contract

The target is a working, reproducible, legally operated system: verified public record -> retained provenance -> normalized entity/site/parcel/permit -> qualified opportunity -> human-reviewed outreach -> documented customer bid request -> approved bid -> contract/outcome -> verified royalty accounting.

No mockup counts, illustrative project photos, source-status inflation, guessed contacts, invented valuations, unverified jobsite activity, or automatically green new source observations.
No bypass of login, CAPTCHA, access restrictions, source terms, usage limits, or rate limits. Respect source-specific permitted access, licensing and reuse conditions; stop and record failures.
The approved UI layout and its acceptance reference remain locked. Nonessential AI is independently optional.

## Engineering order and acceptance evidence

| Workstream | Minimum acceptance evidence |
| --- | --- |
| 0. CI and assurance discipline | Python 3.11/3.12 tests, Ruff, strict mypy, mutation suite, dependency/vulnerability checks and exact-head reports pass. Freeze/review Native Maximum assurance only after integrated runtime is ready. |
| 1. Lawful source inventory and acquisition | Every county/city source has documented access authority, verified endpoint/capabilities, freshness, request envelope, coverage limits, lawful volume bounds, last success/failure and stable source IDs. Start with SB/Riverside pilot sources; blocked sources stay blocked. No blanket countywide-completeness assertion. |
| 2. Intake, change, parcel and identity pipeline | Approved retained observations flow through deterministic normalized snapshots, source-linked APN/geospatial resolution and ambiguity-preserving entity matching. Replays are idempotent, conflicts retained, stale updates blocked and state transitions auditable. |
| 3. Evidence-backed opportunity qualification | Verified current activity, scope, county, identity, security relevance, contact provenance and human review gates determine red/yellow/green. Raw CEQA/permit rows remain unassessed. Every status has explainable reasons and a current source trail. |
| 4. Command Center and map | Owner-approved layout passes real browser/visual inspection. Search, filters, pagination, dossier navigation, retained map state, legends, geo layers and candidate drilldown work at tested data volumes. Geometric accuracy and missing layers are explicitly disclosed. |
| 5. Entity Network and evidence chains | Cross-county relationships and time-ordered evidence preserve sources, role ambiguity, contradictory claims and bounded-query truncation. No unverifiable corporate merges. |
| 6. Persistent watchlist and alerts | Exact watch identities survive restart; source revisions trigger deduplicated material events; authorized scheduler and opted-in alert delivery operate with recorded failures, retry policy and unsubscribe controls. |
| 7. Lead Console and approved outreach | Human-selected qualified leads, durable duplicate suppression, reviewed contact sources, email preview, approval, sender authorization, recorded delivery and responses. Outreach is first; email transport cannot send without an explicit approved effect. |
| 8. Bid Studio | A documented prospect request and scope are prerequisites. Exact-money line items, content-bound internal draft, separate commercial approval, printable approved proposal and explicit customer-delivery effect are independently tested. Never bid automatically from green lead status. |
| 9. Result and Royalty Ledger | Contract and royalty terms, attribution, currency, accrual, invoice, collection, reversal and correction histories are independently verified. A calculated share does not establish a receivable or paid balance. |
| 10. Optional AI Center | Explicit opt-in, privacy and cost disclosure, independent adapter, citations to retained records, bounded context, no silent source mutations or autonomous commercial actions, and graceful operation with AI disabled. |
| 11. Final production trial | Clean install, actual approved source acquisition, retained data ingestion, browser acceptance, restart/replay, failure injection, concurrency, bounded-volume and audit verification; documented operator runbook and rollback. |

## Current milestone

- The 165 historical branches have been classified and reconciled/superseded as documented. This is historical provenance, not runtime release acceptance.
- Ruff regression corrections were committed on PR #201; current-head CI is required before treating them as closed.
- Bid Studio's existing read-only internal proposal draft service is being connected to its request-evidence and exact-money pricing previews in the desktop Command Center. It explicitly cannot authorize or deliver a customer-facing bid.
- Live production source coverage, actual commercial delivery, royalty payment verification, scheduled alerts, full geographic layers, and pixel-accurate browser acceptance remain separate deliverables.
- Remaining Native Maximum Assurance is a release gate after the final frozen runtime tree; do not create premature final assurance on a moving branch.

Each workstream closes only upon retained implementation, replayable tests, exact-head CI and actual relevant end-to-end runtime evidence. Draft PR #201 stays unmerged until separately authorized.
