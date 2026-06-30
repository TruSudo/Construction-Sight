# ConstructionSight

ConstructionSight is a lawful public-record construction intelligence platform focused initially on San Bernardino County and Riverside County, California.

The platform is designed to discover, verify, normalize, store, and analyze public construction, planning, entitlement, CEQA, permit, contractor, parcel, and agenda data. Current implementation is strongest in source-neutral models, deterministic services, evidence-first workflow logic, persistence for core post-enrichment records, source/status/readiness audit reporting, and test-backed architecture. Live source integrations and operator UI remain planned work unless expressly marked otherwise.

## Operating Boundary

ConstructionSight only uses lawful public access methods.

The project does not bypass authentication, captchas, rate limits, access controls, paywalls, robots restrictions, or terms-of-service limits. It does not use credential misuse, hidden/private data, or scraping behind logins unless the user lawfully provides credentials and the source terms permit that access.

## Architecture Principle

ConstructionSight is built around adapter families, not one-off city scrapers.

Initial adapter families:

- CEQAnet
- CSLB
- Accela Citizen Access
- Tyler EnerGov
- Granicus / Legistar
- CivicPlus / PrimeGov
- Laserfiche / PDF repositories
- Custom municipal reports

Adapter contracts are not the same thing as live source integrations. Most adapter families are still placeholder contracts. Source records in `data/source_registry.seed.json` are seed targets and must remain treated as unverified until checked. Run `constructionsight-source-status report data/source_registry.seed.json` before making any source-readiness claim. Run `constructionsight-source-readiness check data/source_registry.seed.json` to produce conservative report-only readiness evidence before any future registry-status change.

## Current Pipeline

```text
lawful public-record intake
  -> evidence preservation
  -> source registry
  -> source status/readiness reporting
  -> source adapter contracts
  -> parcel source registry
  -> parcel source schema preview
  -> parcel row preview
  -> parcel core record
  -> geometry normalization
  -> parcel-backed site resolution
  -> permit snapshot and transition detection
  -> contractor identity
  -> decision records
  -> opportunity enrichment
  -> lead review package
  -> lead dedupe
  -> lead workflow status
  -> result ledger and share calculation
```

See `docs/architecture/current_implementation_status.md` for the implemented-versus-planned matrix and active defect ledger. See `docs/audits/full_repo_audit_inventory.md` for the full repository audit inventory.

## Universal Intake Doctrine

ConstructionSight operates under exhaustive lawful intake and progressive understanding.

Formats are finite. Layouts are variable. Meaning is contextual. Evidence must be preserved. Understanding must be progressive. Normalization must be universal.

Every lawful input should first become preserved evidence and a source-neutral intake record. The intake layer detects the digital format family, extracts recognizable material facts, labels anything unknown or unmapped, and routes the record toward a source adapter, human review, adapter backlog, or lead/opportunity intake.

See `docs/architecture/exhaustive_lawful_intake.md` for the intake contract.

## Source Status and Readiness Doctrine

ConstructionSight separates source status from source readiness.

`constructionsight-source-status report data/source_registry.seed.json` reports what the source registry and adapter metadata currently claim. `constructionsight-source-readiness check data/source_registry.seed.json` produces a conservative, non-mutating readiness report with source key/name, platform family, public URL, lawful-access boundary, verification status, adapter status, optional HTTP reachability, reasons, limitations, next action, timestamp, and JSON output.

Readiness statuses are `seed_only`, `reachable`, `blocked`, `failed`, `partial`, and `verified_candidate`. A reachable URL is not the same thing as verified usable source coverage.

See `docs/architecture/source_readiness_workflow.md` for the readiness contract.

## Opportunity Transition Doctrine

ConstructionSight treats the transition event as the actionable sales signal.

A static permit or CEQA record matters because it can expose movement: a new project signal, CEQA notice, permit application, issued permit, contractor identification, valuation signal, inspection movement, expiration, finalization, site anchor, contact channel, agency anchor, or construction-scope signal.

Universal intake records can now be converted into source-neutral opportunity candidates with transition events, lead score, readiness, priority, reasons, limitations, confidence band, and recommended next action.

See `docs/architecture/opportunity_transition_intake.md` for the opportunity candidate contract.

## External Intelligence Capability Doctrine

ConstructionSight lawfully studies Shovels and Regrid as capability targets, not as protected implementations to copy.

Shovels-style intelligence teaches the product to model permits, contractors, contractor groups, addresses, parcels, properties, residents, employees, universal people, decisions, and first-seen/status-change timelines as an entity graph. Regrid-style intelligence teaches the product to treat parcel geometry as the stable land identity object: geometry to canonical parcel to owner to portfolio to development activity.

The implementation target is better than static aggregation: preserved source evidence, normalized records, identity resolution, field diffs, transition events, opportunity candidates, project graph, lead score, review package, dedupe, workflow status, result ledger, and audit trail.

See `docs/architecture/external_intelligence_capability_spine.md` for the Shovels/Regrid capability matrix and gap-report contract.

## Shovels/Regrid Gap Alignment Doctrine

ConstructionSight separates Shovels and Regrid into different architectural roles.

Regrid-style capability is the parcel and geometry spine: stable parcel identity, parcel paths, parcel schema, GeoJSON geometry, tiles, feature service, batch lookup, bulk delivery, zoning, ownership, building, address, and roadway add-ons.

Shovels-style capability is the construction-activity overlay: permits, permit status/lifecycle data, contractor search, contractor employees, contractor metrics, address search, residents, decisions, coverage metadata, release metadata, GIS, CLI, API, and warehouse delivery.

ConstructionSight's native advantage is the timing layer above both: transition detection, evidence-backed opportunity scoring, review workflow, duplicate suppression, confidence transparency, limitations preservation, and result/share tracking.

See `docs/architecture/shovels_regrid_gap_alignment.md` and run `constructionsight-shovels-regrid-gaps` for the research-aligned gap matrix and implementation roadmap.

## Parcel/Site Resolution Doctrine

ConstructionSight treats parcel and site identity as the land anchor for every public-record lead.

APNs, addresses, coordinates, geometry, jurisdiction, and county hints are normalized into source-neutral site-resolution candidates with deterministic `site:` keys, match strength, confidence, reasons, limitations, and conflict preservation. This is the Regrid-style backbone that later lets permits, CEQA records, agendas, staff reports, contractors, owners, zoning, and workflow territories snap to a common project/site graph.

See `docs/architecture/parcel_site_resolution_spine.md` for the parcel/site resolution contract.

## Parcel Source Registry Doctrine

ConstructionSight does not treat a county parcel layer, licensed provider, open-data portal, or user-provided file as import-ready until its lawful boundary, coverage, schema, geometry support, and field mappings are represented.

The parcel source registry separates source targets from verified imports. It tracks provider type, access boundary, coverage status, source format, expected field roles, geometry support, limitations, priority, and next action. This creates the control surface required before live parcel ingestion, geometry normalization, and site-resolution enrichment.

See `docs/architecture/parcel_source_registry.md` for the parcel source registry contract.

## Parcel Source Schema Preview Doctrine

ConstructionSight previews parcel source schemas before import.

A parcel source or file must expose enough fields to map APN, county, and high-value roles such as address, owner, zoning, land use, geometry, source record ID, and updated timestamp. Schema preview reports observed fields, inferred canonical roles, missing required roles, unmapped fields, geometry support, spatial reference, limitations, status, and next action.

See `docs/architecture/parcel_source_schema_preview.md` and run `constructionsight-parcel-sources preview-schema` for the pre-import schema gate.

## Parcel Row Preview Doctrine

ConstructionSight previews candidate parcel rows before creating parcel records.

Mapped rows must contain usable APN and county values, can normalize APNs and addresses, can flag geometry presence, and must preserve row-level limitations. Row preview reports usable and skipped counts without writing records, allowing bad rows and missing mappings to be corrected before parcel core record and geometry normalization are built.

See `docs/architecture/parcel_row_preview.md` and run `constructionsight-parcel-sources preview-rows` for the pre-record row gate.

## Parcel Core Record Doctrine

ConstructionSight creates parcel core records only after schema and row preview gates.

The first canonical parcel object preserves source key, source record ID, APN, normalized APN, county, optional address, optional zoning/land-use hints, optional geometry summary, geometry hash, centroid, envelope, spatial reference, and limitations. Ownership/contact enrichment is intentionally deferred so the land-identity spine remains clean, lawful, and source-neutral.

See `docs/architecture/parcel_core_record_geometry.md` for the parcel core record and geometry normalization contract.

## Parcel-Backed Site Resolution Doctrine

ConstructionSight resolves site hints against parcel core records when available.

APN, address, and coordinate hints can produce parcel-backed site candidates with confidence, reasons, geometry-derived coordinates, ambiguity preservation, and fallback to hint-only resolution when no parcel core record matches. Polygon and multipolygon coordinate matches preserve limitations because current containment is envelope-only, not topology-grade point-in-polygon proof.

See `docs/architecture/parcel_backed_site_resolution.md` for the parcel-backed site resolution contract.

## Permit Snapshot Transition Doctrine

ConstructionSight detects movement by comparing permit snapshots.

A source-neutral permit snapshot captures record identity, permit number, status, key dates, value, contractor signals, and site key. Transition detection emits first-seen, status, value, contractor, date, site, and description changes.

See `docs/architecture/permit_snapshot_transition_spine.md` for the permit movement contract.

## Contractor Identity Doctrine

ConstructionSight treats contractor identity as a conservative source-neutral match layer.

Contractor names, license numbers, license status, classifications, group signals, reasons, confidence, and limitations are normalized before contractor signals are used by opportunity enrichment.

See `docs/architecture/contractor_identity_spine.md` for the contractor identity contract.

## Decision Record Doctrine

ConstructionSight treats CEQA records, agenda items, staff reports, planning hearings, and public decision signals as pre-permit opportunity evidence.

Decision records preserve source kind, decision kind, title, normalized title, APN/site hints, applicant/developer signals, confidence, reasons, and limitations.

See `docs/architecture/decision_record_spine.md` for the decision record contract.

## Opportunity Enrichment Doctrine

ConstructionSight combines parcel/site, permit transition, contractor identity, and decision signals into explainable opportunity enrichment reports.

Every score contribution must come from a named signal with a reason, confidence score, and limitations. Enrichment reports also preserve scoring profile key/version so future tuning does not silently change the meaning of historical scores.

See `docs/architecture/opportunity_enrichment_spine.md` for the enrichment contract.

## Lead Review, Dedupe, Workflow, and Result Doctrine

ConstructionSight separates scoring from operator review and later workflow states.

The current post-enrichment spine is:

```text
OpportunityEnrichmentReport
  -> LeadReviewPackage
  -> LeadFingerprint / LeadDuplicateResult
  -> LeadWorkflowRecord / LeadWorkflowEvent
  -> ResultLedgerRecord / ResultShareRecord
```

Lead workflow status changes are matrix-constrained, and final statuses have no outgoing transitions unless a later explicit override/reopen doctrine is added. Result ledgers preserve explicit share states: `not_applicable`, `pending_gross_value`, `pending_share_rate`, and `calculated`.

See:

- `docs/architecture/lead_review_package.md`
- `docs/architecture/lead_dedupe.md`
- `docs/architecture/lead_workflow_status.md`
- `docs/architecture/result_ledger.md`

## Known Limitations

- SQLAlchemy ORM/storage coverage now exists for movement, identity, parcel core, site-resolution reports, and post-enrichment lead workflow records. Remaining storage gaps are optional preview-report archives and optional nested child tables.
- Most adapter families are placeholder contracts, not live source integrations.
- Source registry seed records remain unverified until checked; source-status reporting currently shows four seed-only records and zero verified usable sources, and source-readiness reports do not mutate registry status.
- Geometry containment currently has first-pass limitations and must not be treated as survey-grade parcel topology.
- Opportunity scoring uses a versioned default profile; additional profiles must be introduced explicitly with doctrine and tests.
- Lead workflow transitions preserve event history and are constrained by a status matrix; override/reopen behavior is not implemented.
- Result ledgers distinguish pending gross value, pending share rate, calculated share, and not-applicable share states; business-specific share enforcement remains future work.
- Persisted model/service layers now have storage-summary visibility and source maturity has source-status/source-readiness visibility; dedicated action/list/detail operator CLIs remain pending.
- No external outreach-sending behavior is implemented or implied.

## Forward Cleanup Doctrine

Every future feature PR must include a cleanup review before merge. New models and services must be checked for tests, documentation, persistence needs, CLI needs, lawful-access boundaries, reasons, confidence, limitations, and doctrine/runtime impact.

Do not claim Regrid or Shovels parity merely because model layers exist. Parity requires lawful source coverage, live adapter maturity, persistence, operator workflow, and verified results.

## Phase 1 Status

Repository foundation initialized. CEQAnet public-record intake has guarded operator and archive tooling, but CEQAnet remains contract-ready rather than live production coverage. Universal intake, source-status/readiness reporting, opportunity transition intake, parcel/site resolution, parcel source registry, schema preview, row preview, parcel core record, geometry normalization, parcel-backed site resolution, permit transitions, contractor identity, decision records, opportunity enrichment, lead review, dedupe, workflow status, result ledger, and storage-summary reporting now exist as tested model/service/operator-support architecture. The next required cleanup phases are topology-grade geometry, dedicated action/list/detail operator CLIs, explicit registry update/dry-run workflow if source promotion is needed, optional preview archive persistence, and any future business-specific share enforcement.
