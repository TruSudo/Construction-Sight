# ConstructionSight

ConstructionSight is a lawful public-record construction intelligence platform focused initially on San Bernardino County and Riverside County, California.

The platform is designed to discover, verify, normalize, store, and analyze public construction, planning, entitlement, CEQA, permit, contractor, parcel, and agenda data.

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

## Universal Intake Doctrine

ConstructionSight operates under exhaustive lawful intake and progressive understanding.

Formats are finite. Layouts are variable. Meaning is contextual. Evidence must be preserved. Understanding must be progressive. Normalization must be universal.

Every lawful input should first become preserved evidence and a source-neutral intake record. The intake layer detects the digital format family, extracts recognizable material facts, labels anything unknown or unmapped, and routes the record toward a source adapter, human review, adapter backlog, or lead/opportunity intake.

See `docs/architecture/exhaustive_lawful_intake.md` for the intake contract.

## Opportunity Transition Doctrine

ConstructionSight treats the transition event as the actionable sales signal.

A static permit or CEQA record matters because it can expose movement: a new project signal, CEQA notice, permit application, issued permit, contractor identification, valuation signal, inspection movement, expiration, finalization, site anchor, contact channel, agency anchor, or construction-scope signal.

Universal intake records can now be converted into source-neutral opportunity candidates with transition events, lead score, readiness, priority, reasons, limitations, confidence band, and recommended next action.

See `docs/architecture/opportunity_transition_intake.md` for the opportunity candidate contract.

## External Intelligence Capability Doctrine

ConstructionSight lawfully studies Shovels and Regrid as capability targets, not as protected implementations to copy.

Shovels-style intelligence teaches the product to model permits, contractors, contractor groups, addresses, parcels, properties, residents, employees, universal people, decisions, and first-seen/status-change timelines as an entity graph. Regrid-style intelligence teaches the product to treat parcel geometry as the stable land identity object: geometry to canonical parcel to owner to portfolio to development activity.

The implementation target is better than static aggregation: preserved source evidence, normalized records, identity resolution, field diffs, transition events, opportunity candidates, project graph, lead score, outreach preview, and audit trail.

See `docs/architecture/external_intelligence_capability_spine.md` for the Shovels/Regrid capability matrix and gap-report contract.

## Shovels/Regrid Gap Alignment Doctrine

ConstructionSight separates Shovels and Regrid into different architectural roles.

Regrid-style capability is the parcel and geometry spine: stable parcel identity, parcel paths, parcel schema, GeoJSON geometry, tiles, feature service, batch lookup, bulk delivery, zoning, ownership, building, address, and roadway add-ons.

Shovels-style capability is the construction-activity overlay: permits, permit status/lifecycle data, contractor search, contractor employees, contractor metrics, address search, residents, decisions, coverage metadata, release metadata, GIS, CLI, API, and warehouse delivery.

ConstructionSight's native advantage is the timing layer above both: transition detection, evidence-backed opportunity scoring, outreach preview, confidence transparency, and limitations preservation.

See `docs/architecture/shovels_regrid_gap_alignment.md` and run `constructionsight-shovels-regrid-gaps` for the research-aligned gap matrix and implementation roadmap.

## Parcel/Site Resolution Doctrine

ConstructionSight treats parcel and site identity as the land anchor for every public-record lead.

APNs, addresses, coordinates, geometry, jurisdiction, and county hints are normalized into source-neutral site-resolution candidates with deterministic `site:` keys, match strength, confidence, reasons, limitations, and conflict preservation. This is the Regrid-style backbone that later lets permits, CEQA records, agendas, staff reports, contractors, owners, zoning, and outreach territories snap to a common project/site graph.

See `docs/architecture/parcel_site_resolution_spine.md` for the parcel/site resolution contract.

## Parcel Source Registry Doctrine

ConstructionSight does not treat a county parcel layer, licensed provider, open-data portal, or user-provided file as import-ready until its lawful boundary, coverage, schema, geometry support, and field mappings are represented.

The parcel source registry separates source targets from verified imports. It tracks provider type, access boundary, coverage status, source format, expected field roles, geometry support, limitations, priority, and next action. This creates the control surface required before live parcel ingestion, geometry normalization, and site-resolution enrichment.

See `docs/architecture/parcel_source_registry.md` for the parcel source registry contract.

## Parcel Source Schema Preview Doctrine

ConstructionSight previews parcel source schemas before import.

A parcel source or file must expose enough fields to map APN, county, and high-value roles such as address, owner, zoning, land use, geometry, source record ID, and updated timestamp. Schema preview reports observed fields, inferred canonical roles, missing required roles, unmapped fields, geometry support, spatial reference, limitations, status, and next action.

See `docs/architecture/parcel_source_schema_preview.md` and run `constructionsight-parcel-sources preview-schema` for the pre-import schema gate.

## Phase 1 Status

Repository foundation initialized. CEQAnet public-record intake now has a guarded operator lane and archive verification. Universal intake now preserves lawful inputs, detects format families, extracts material facts, and routes records. Opportunity transition intake converts extracted facts into lead candidates for enrichment, deduplication, monitoring, outreach preview, and later bid workflows. External intelligence capability tracking maps Shovels/Regrid parity, licensed blockers, and ConstructionSight outperform targets. Shovels/Regrid gap alignment now encodes the research-backed roadmap: Regrid as parcel/geometry spine, Shovels as permit/contractor/decision overlay, and ConstructionSight as the timing/opportunity layer. Parcel/site resolution anchors APN, address, coordinate, geometry, jurisdiction, and county signals into deterministic site keys for graph expansion. Parcel source registry tracks source targets, lawful boundaries, coverage status, field mappings, and provider readiness before live import. Parcel source schema preview now validates observed fields and inferred canonical roles before parcel import preview.
