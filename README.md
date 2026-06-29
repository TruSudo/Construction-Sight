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

## Phase 1 Status

Repository foundation initialized. CEQAnet public-record intake now has a guarded operator lane and archive verification. Universal intake now preserves lawful inputs, detects format families, extracts material facts, and routes records. Opportunity transition intake converts extracted facts into lead candidates for enrichment, deduplication, monitoring, outreach preview, and later bid workflows. External intelligence capability tracking now maps Shovels/Regrid parity, licensed blockers, and ConstructionSight outperform targets.
