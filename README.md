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

## Phase 1 Status

Repository foundation initialized. CEQAnet public-record intake now has a guarded operator lane and archive verification. The next product spine is universal intake: source-neutral evidence preservation, format-family detection, material-fact extraction, and routing into future lead/opportunity workflows.
