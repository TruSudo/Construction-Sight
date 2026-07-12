# ConstructionSight

ConstructionSight is a lawful public-record construction intelligence platform focused initially on San Bernardino County and Riverside County, California.

The system is designed to discover, preserve, normalize, resolve, score, review, and track public construction signals across CEQA, permits, contractors, parcels, planning decisions, and related government records. The current implementation is strongest in governed backend architecture, evidence preservation, domain models, persistence, operator CLI surfaces, parcel/site reasoning, workflow controls, and repository certification. Production recurring source collection, outreach, and the graphical operator application remain planned work unless explicitly stated otherwise.

## Operating boundary

ConstructionSight uses lawful public access methods only.

It does not bypass authentication, captchas, rate limits, HTTP access controls, paywalls, robots restrictions, or terms-of-use limits. It does not disguise an automated client to defeat a source response. Credentials may be used only when lawfully supplied and permitted by the source.

## Source maturity

Adapter contracts are not equivalent to verified live integrations.

The canonical source registry currently contains:

- CEQAnet State Clearinghouse: `partial`
- CSLB Public License Search: `unverified`
- San Bernardino County EZOP: `unverified`
- Riverside County PLUS Online: `unverified`

CEQAnet is classified `partial` because its official entry, advanced search, result-list, project-summary, document-detail, policy, and CSV-export surfaces were reviewed and recorded. Bounded automated HTML collection later received HTTP 403. No bypass was attempted. The existing recurring-run service remains verified-only, so `partial` status does not authorize live recurring execution.

The preferred next CEQAnet integration target is a bounded source-provided CSV contract or source-specific access clarification, followed by a separate controlled promotion to `verified`.

See:

- `evidence/source_verification/ceqanet_public_access_2026-07-12.json`
- `evidence/source_verification/ceqanet_checklist_2026-07-12.json`
- `docs/audits/ceqanet_source_verification_2026-07-12.md`
- `docs/architecture/current_implementation_status.md`
- `docs/audits/full_repo_audit_inventory.md`

## Architecture principle

ConstructionSight is built around source-neutral evidence and reusable adapter families rather than isolated municipal scrapers.

Registered adapter families include:

- CEQAnet
- CSLB
- Accela Citizen Access
- Tyler EnerGov
- Granicus / Legistar
- CivicPlus / PrimeGov
- Laserfiche / document repositories
- Custom municipal reports

Most adapter families remain contracts or planned integrations. Source maturity, reachability, adapter readiness, verified coverage, and production operation are represented separately.

## Current pipeline

```text
lawful public-record intake
  -> evidence preservation
  -> source registry and maturity governance
  -> readiness, audit, checklist, plan, and controlled apply
  -> source-neutral normalization
  -> parcel/site identity and topology reasoning
  -> permit transition, contractor, and public-decision signals
  -> opportunity enrichment
  -> lead review and duplicate suppression
  -> governed lead workflow
  -> immutable result and share authority
```

The current recurring CEQAnet boundary is:

```text
current registry + current checklist evidence
  -> exact-schema run definition
  -> exact-window manifest
  -> explicit per-attempt authorization
  -> bounded GET-only execution
  -> digest-bound verification
```

That boundary requires a registry status of `verified`. CEQAnet currently remains below that threshold.

## Implemented capabilities

### Source governance

- Source registry and source-status reporting
- Readiness reports and audit packages
- Manual verification checklists and evidence references
- Deterministic promotion and registry-update plans
- Explicit digest-bound, status-only controlled apply
- CEQAnet browser-review evidence and partial-maturity classification
- Exact-schema CEQAnet recurring-run definitions, manifests, executions, and verification
- Stale-registry and stale-checklist rejection
- Whole-execution-envelope digest verification
- Exact request reconstruction and ordered page-coverage checks

### Intelligence and domain layers

- Source-neutral lawful intake
- Opportunity transition candidates
- Parcel-source registry, schema preview, and row preview
- Parcel core records with GeoJSON and WKT/EWKT support
- Polygon and multipolygon topology with holes and separate parts
- Source-plane area-weighted centroids
- Conservative CRS conflict and incompatibility handling
- Parcel-backed site resolution
- Permit snapshots and transition detection
- Contractor identity
- Public-decision records
- Versioned opportunity scoring
- Lead review packages and duplicate detection

### Workflow and persistence

- Dedicated ORM/store coverage for core upstream and post-enrichment records
- Read-only upstream list/detail inspection
- Matrix-constrained lead workflow transitions
- Append-only workflow events
- Immutable result-ledger revisions
- Explicit result-share states
- Compare-and-swap result authority with append-only authority events
- Backward-compatible reading of historical result payloads

### Quality and governance

- Ruff with no ignored rules
- Strict mypy
- Warning-strict pytest
- Python 3.11 and 3.12 CI
- Adapter-contract and source-coverage audits
- Complete tracked-tree repository certification
- Clean-worktree and diff-hygiene enforcement
- Separate active-defect, resolved-defect, and planned-capability ledgers

## Operator commands

Representative command surfaces include:

```text
constructionsight
constructionsight-source-status
constructionsight-source-readiness
constructionsight-audit-package
constructionsight-source-verification
constructionsight-source-promotion-plan
constructionsight-source-registry-plan
constructionsight-source-registry-apply
constructionsight-ceqanet-recurring-run
constructionsight-upstream
constructionsight-leads
constructionsight-results
constructionsight-certify
```

Mutation commands require explicit authorization and stale-state validation where supported. Generic upstream mutation is intentionally unavailable.

## Parcel and geometry boundary

Parcel identity is the land anchor for project convergence.

The current geometry layer recognizes supported GeoJSON and WKT/EWKT Point, Polygon, and MultiPolygon input. It preserves rings, holes, parts, raw geometry, hashes, supplied or embedded CRS, conflicts, bounds, centroid limitations, and fallback reasons.

Projected or conflicting coordinates are not mislabeled or compared as longitude/latitude. CRS transformation, projection-aware or geodesic calculation, topology repair, and survey-grade boundary conclusions are not implemented.

## Commercial workflow boundary

The backend can represent and govern opportunities, leads, workflow state, results, and royalty/share outcomes. It does not yet:

- continuously collect verified production source data;
- maintain a production attempt ledger or scheduler;
- autonomously enrich all decision-maker contacts;
- send outreach;
- create or send bids; or
- provide the planned graphical operator application.

No external communication behavior is implied by the existing models or CLI.

## Known limitations

- CEQAnet is `partial`, not `verified`; automated HTML collection received HTTP 403.
- Official CEQAnet CSV links are documented but have not yet been implemented as a governed ingestion contract.
- The other three canonical sources remain unverified.
- Verified usable source coverage remains zero.
- Most adapter families remain contract-level.
- Optional preview archives and nested child tables remain unimplemented.
- Generic upstream corrections remain blocked pending record-family-specific doctrine.
- Lead workflow reopen or override behavior is not implemented.
- Outreach and GUI capabilities are not implemented.
- Geometry results are not survey-grade legal proof.

## Development doctrine

Every feature phase must be narrow, evidence-backed, reviewable, reversible, and tested on the exact final tree. Known defects block feature work. Planned capabilities must not be mislabeled as defects, and missing capabilities must not be represented as implemented.

Before merge, each phase must reconcile:

- runtime behavior;
- tests and static analysis;
- persistence;
- operator exposure;
- lawful-access boundaries;
- provenance and limitations;
- documentation and source maturity;
- compatibility; and
- repository certification.

See `docs/architecture/current_implementation_status.md` and `docs/audits/full_repo_audit_inventory.md` for the authoritative implementation and audit state.
