# ConstructionSight

ConstructionSight is a lawful public-record construction intelligence platform focused initially on San Bernardino County and Riverside County, California.

The system is designed to discover, preserve, normalize, resolve, score, review, and track public construction signals across CEQA, permits, contractors, parcels, planning decisions, and related government records. The current implementation is strongest in governed backend architecture, evidence preservation, domain models, persistence, operator CLI surfaces, parcel/site reasoning, workflow controls, and repository certification. A local read-only graphical operator application and a separate, explicitly confirmed local source-review staging CLI are implemented on draft integration PR #119; neither is merged to main or production-certified. The GUI is not browser-verified, the staging CLI retains unapproved normalized-source snapshots only, and no commercial opportunity, outreach or bid is authorized. Production recurring source collection and commercial outreach remain planned integration work. See docs/architecture/operator_gui.md for exact limitations.

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

ConstructionSight has an official CSV contract that plans exact project/document export URLs, validates already-obtained CSV bytes, and performs one explicitly authorized bounded GET with no retry. The original HTTP 200 proof failed under the former UTF-8-only parser and remains preserved. An offline replay of the exact retained body now passes as Windows-1252 with 2 source rows and an independently verified replay digest. A digest-bound maturity proposal independently verifies that evidence and records `keep_partial`. A separate expiring official-CSV policy now permits only explicit, one-request, zero-retry evidence collection; it does not authorize production recurring execution or promotion. A governed evidence-series ledger now enforces the policy window, one execution per UTC day, exact execution/body/verification bindings, access-control halt finality, and readiness criteria. Sequence 1 now contains one independently verified project observation from UTC 2026-07-14; the source remains `partial` and no second request is permitted that day.

See:

- `evidence/source_verification/ceqanet_public_access_2026-07-12.json`
- `evidence/source_verification/ceqanet_checklist_2026-07-12.json`
- `docs/audits/ceqanet_source_verification_2026-07-12.md`
- `docs/architecture/ceqanet_official_csv_contract.md`
- `evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json`
- `evidence/source_verification/ceqanet_csv_live_verification_2026-07-12.json`
- `docs/audits/ceqanet_csv_live_proof_2026-07-12.md`
- `evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json`
- `evidence/source_verification/ceqanet_csv_windows1252_replay_verification_2026-07-12.json`
- `docs/audits/ceqanet_csv_windows1252_replay_2026-07-12.md`
- `evidence/source_verification/ceqanet_source_maturity_proposal_2026-07-13.json`
- `evidence/source_verification/ceqanet_source_maturity_proposal_verification_2026-07-13.json`
- `docs/audits/ceqanet_source_maturity_proposal_2026-07-13.md`
- `docs/architecture/ceqanet_source_maturity_proposal.md`
- `evidence/source_verification/ceqanet_csv_access_policy_2026-07-14.json`
- `evidence/source_verification/ceqanet_csv_access_policy_verification_2026-07-14.json`
- `docs/audits/ceqanet_csv_access_policy_2026-07-14.md`
- `docs/architecture/ceqanet_csv_access_policy.md`
- `evidence/source_verification/ceqanet_csv_evidence_series_2026-07-14.json`
- `evidence/source_verification/ceqanet_csv_evidence_series_verification_2026-07-14.json`
- `docs/audits/ceqanet_csv_evidence_series_2026-07-14.md`
- `docs/architecture/ceqanet_csv_evidence_series.md`
- `evidence/source_verification/ceqanet_csv_evidence_execution_2026-07-14_project.json`
- `evidence/source_verification/ceqanet_csv_evidence_series_2026-07-14_sequence_1.json`
- `evidence/source_verification/ceqanet_csv_evidence_series_verification_2026-07-14_sequence_1.json`
- `docs/audits/ceqanet_csv_evidence_observation_2026-07-14.md`
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
  -> append-only parcel observations and governed current selection
  -> field-level parcel claim assurance
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

The official CSV boundary has separate offline and one-request proof layers:

```text
10-digit SCH number + optional document ID
  -> exact official CSV URL identity
  -> either already-obtained CSV bytes
     or explicit one-GET/no-retry live authorization
  -> complete response-envelope retention
  -> content-type, encoding, header, row, and SCH validation
  -> body hash + bounded normalized rows + inspection digest
  -> independent offline execution verification
```

Planning, local inspection, and execution verification are offline. Live proof requires explicit authorization for one request and never authorizes attachment download, persistence mutation, retries, or scheduling.

The governed evidence-series boundary is:

```text
verified current policy + verified current series
  -> explicit per-execution authorization
  -> one official CSV GET on an unused UTC date
  -> complete policy-bound execution artifact
  -> independent live verification
  -> immutable compact observation
  -> collecting, halted, or maturity-review-ready series snapshot
```

The canonical series head is sequence 1 with one successful project observation
on UTC 2026-07-14. The build and verify commands are offline; only the
explicitly authorized execute command is network-capable.

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
- Exact official CEQAnet project/document CSV URL planning
- Offline CSV media-type, UTF-8/BOM, schema, row-width, SCH, and digest validation
- One-request CEQAnet CSV live-proof execution with explicit authorization and no retries
- Strict UTF-8-first and explicit Windows-1252 fallback for source-provided CSV
- Offline encoding replay linked to the original execution digest and body hash
- Digest-bound, report-only CEQAnet maturity proposals with a fixed `keep_partial` decision
- Expiring official-CSV evidence policies with one-request, zero-retry authority
- Immutable official-CSV evidence-series snapshots with policy-bound executions, one-per-UTC-day enforcement, terminal access-control halts, and report-only maturity readiness
- Complete response-byte, URL, status, header, body-hash, and inspection evidence
- Independent offline verification of the retained live execution envelope
- Preservation of original, normalized, canonical-role, and unknown CSV columns

### Intelligence and domain layers

- Source-neutral lawful intake
- Opportunity transition candidates
- Parcel-source registry, schema preview, and row preview
- Official county ArcGIS capability snapshots and four-request bounded probe plans
- Retained portable county bounded-proof bundles with offline verification and exact-ID persistence receipts
- Structured bulk-rehearsal page, checkpoint, resume, and retry evidence that prevents boolean-only proof claims
- Governed complete-rehearsal executor with exact count/page response retention, durable checkpoint reload, resumed-segment fault injection, bounded retry, and count reconciliation
- Digest-bound official ArcGIS rehearsal plans and an exact-response HTTP adapter with one-request transport semantics and fail-closed redirect, endpoint, media-type, size, JSON, and service-error controls
- Self-contained complete-rehearsal proof bundles with embedded exact response bytes, atomic exact-ID save/replay, and independent offline plan, manifest, receipt, and object-ID recomputation
- Expiring single-use ArcGIS live-rehearsal authorization and offline preflight bound to one exact plan, with import, promotion, recurring, credential, bypass, and production-bulk authority fixed false
- Parcel core records with GeoJSON and WKT/EWKT support
- Polygon and multipolygon topology with holes and separate parts
- Source-plane area-weighted centroids
- Conservative CRS conflict and incompatibility handling
- Parcel-backed site resolution
- Immutable parcel observations with complete and content SHA-256 identities
- Source-effective/observed-time current selection with explicit supersession
- Assurance withholding for mixed-time or same-time-content ambiguity
- Field-level parcel claims with explicit authority and source-dependency lineage
- Explainable agreement, corroboration, conflict, and missing-evidence outcomes
- Permit snapshots and transition detection
- Contractor identity
- Public-decision records
- Versioned opportunity scoring
- Lead review packages and duplicate detection

### Workflow and persistence

- Dedicated ORM/store coverage for core upstream and post-enrichment records
- Append-only parcel-observation and immutable current-selection persistence
- Additive parcel-assurance report persistence with complete claim payloads
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
constructionsight-ceqanet-csv
constructionsight-ceqanet-maturity
constructionsight-ceqanet-access-policy
constructionsight-ceqanet-evidence-series
constructionsight-parcel-sources
constructionsight-upstream
constructionsight-leads
constructionsight-results
constructionsight-certify
```

Mutation commands require explicit authorization and stale-state validation where supported. Generic upstream mutation is intentionally unavailable.

## Parcel and geometry boundary

Parcel identity is the land anchor for project convergence.

The current geometry layer recognizes supported GeoJSON and WKT/EWKT Point, Polygon, and MultiPolygon input. It preserves rings, holes, parts, raw geometry, hashes, supplied or embedded CRS, conflicts, bounds, centroid limitations, and fallback reasons.

The longitudinal parcel layer wraps complete canonical records in immutable digest-bound observations. It selects current evidence per source using source-effective time only when that clock is complete, falls back to observation time only when source-effective time is entirely absent, records supersession explicitly, and withholds assurance when time bases or leading content are ambiguous.

The parcel-source verification layer binds the official San Bernardino and Riverside public parcel endpoints and observed schemas to immutable evidence, proposition-specific authority, source-scope county/state constants, and an explicit county coverage-gap report. The additive ArcGIS acquisition layer binds exact capability metadata, safe four-request probe plans, executed observations, complete-rehearsal manifests, and explicit maturity assessments. It includes a reusable read-only complete-rehearsal executor, exact-response HTTP adapter, and self-contained portable proof bundle with independent offline recomputation. An expiring single-use authorization and offline preflight now bind any future live rehearsal to one exact snapshot and plan, a maximum 24-hour window, one execution, two count requests, mandatory response/checkpoint/bundle retention, and preserved false authority for credentials, bypass, import, promotion, recurrence, and production bulk collection. No county authorization artifact has been issued or committed, no durable consumption ledger or live execution command exists, and no live county complete rehearsal has been performed. Canonical 2026-07-14 evidence records both official sources as `bounded_query_verified`: San Bernardino reported 839,794 records and Riverside reported 846,251 records, and each exact four-observation bundle independently verifies and passed exact-ID transactional persistence. Neither source is import-ready, bulk-rehearsal-verified, profile-promoted, or bulk-authorized.

The parcel-assurance layer consumes either a caller-supplied governed current set or the output of longitudinal selection without modifying canonical records. It preserves field-level source claims, dependency lineage, proposition-specific authority, timestamps, conflicts, missing evidence, and limitations. Multiple publications of one upstream dataset do not count as independent corroboration, and no opaque global truth score is emitted.

Projected or conflicting coordinates are not mislabeled or compared as longitude/latitude. CRS transformation, projection-aware or geodesic calculation, topology repair, and survey-grade boundary conclusions are not implemented.

## Commercial workflow boundary

The backend can represent and govern opportunities, leads, workflow state, results, and royalty/share outcomes. It does not yet:

- continuously collect verified production source data;
- maintain a production attempt ledger or scheduler;
- autonomously enrich all decision-maker contacts;
- send outreach;
- create or send bids; or
- provide the complete planned graphical operator application.

A local read-only operator GUI now reads persisted CEQA/permit records and lead
workflows. It provides database-backed search, source evidence, named parties,
and an offline geographic coordinate map. Source records are not qualified leads;
no automatic acquisition, outreach, or bid action is enabled. See
[local operator application](docs/architecture/operator_gui.md) for the launch
command, data requirements, precise boundaries, and remaining integration.

No external communication behavior is implied by the existing models, CLI, or GUI.

## Known limitations

- Draft PR #117 remains uncertified. Its current hardening work includes active defects `CS-SR-001` through `CS-SR-074` (74 records) and a separately missing Native Maximum Assurance report. The September 18 historical hardening CI checkpoint reported 1,473 passing pytest tests per supported interpreter and 74 certification findings at its THEN head (73 active defects and the missing assurance report). September 20 exact-head integration verification added 42 test passes per runtime at the earlier GUI head; the historical results do not certify subsequent source-tree changes. The AnyIO advisory remediation is committed to both draft branches and was separately checked by fresh isolated vulnerability audits; no active defect is closed or production release authorized.
- The earlier CS-SR-037/038 fixes and subsequent hardening candidates remain part of the historical review trail. CS-SR-073 is an active P0 pre-gate build-execution defect; no active defect may be closed merely because an implementation or routine quality gate passes. Fresh exact-tree Native Maximum Assurance and authenticated owner acceptance remain outstanding.
- CEQAnet is `partial`, not `verified`; automated HTML collection received HTTP 403.
- The original UTF-8 inspection failure remains preserved; the derived Windows-1252 replay passes against the same retained body hash without a second request.
- Two retained point-in-time CSV successes, including one governed sequence observation, still do not establish recurring availability, completeness, or broader source coverage.
- The maturity-proposal workflow binds that evidence but cannot promote the registry or authorize recurring execution.
- The CSV access policy permits only explicit evidence runs and expires on 2026-08-13; it is not production scheduler authority.
- The independently verified evidence-series head contains one successful project observation; three additional successful observations on later unused UTC dates, including the document export scope, remain required before another maturity review.
- The other three canonical sources remain unverified.
- Verified usable source coverage remains zero.
- Most adapter families remain contract-level.
- Parcel longitudinal selection evaluates only supplied observations; it does not acquire countywide data, establish source coverage or freshness, prove legal title, or resolve same-time content conflicts.
- Official county parcel-source profiles, capability observations, retained bounded four-response proofs, and rehearsal artifacts do not establish complete countywide ingestion or production bulk authority. San Bernardino lacks address/land-use coverage in its retained profile; Riverside lacks owner/jurisdiction/zoning/planning land-use coverage. Both still need independently validated completeness, applicable lawful authority, and separately governed promotion before production acquisition.
- Optional preview archives and nested child tables remain unimplemented.
- Generic upstream corrections remain blocked pending record-family-specific doctrine.
- Lead workflow reopen or override behavior is not implemented.
- Outreach and the full operator application remain incomplete; the local GUI is a read-only development view of retained records.
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
