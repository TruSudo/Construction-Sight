# Source Discovery, Coverage Expansion, and Enrichment Orchestration Model

## Status

Accepted design direction.

## Purpose

ConstructionSight depends on a continuous lawful public-source discovery and enrichment process. The system must know which jurisdictions and sources it actively monitors, how sources are discovered, how refreshes are scheduled, how new or changed records are detected, how enrichment targets are selected, and how failures are explained.

This model defines how ConstructionSight should feed the regional construction pulse, relationship graph, project clustering engine, authority enrichment process, and search-driven enrichment without uncontrolled geographic or source sprawl.

## Core Rule

ConstructionSight should continuously discover, verify, refresh, and enrich public construction intelligence sources, but only within governed coverage rules.

The system must distinguish:

- active operational-zone monitoring;
- watchlist monitoring;
- out-of-zone relationship-horizon references;
- user-directed targeted enrichment;
- rejected or unsupported sources.

## Source Discovery Goals

Source discovery should identify lawful public pathways to construction-relevant data.

Relevant sources may include:

- permit portals;
- planning portals;
- inspection portals;
- CEQA records;
- State Clearinghouse records;
- agenda packets;
- staff reports;
- public hearing notices;
- development activity reports;
- GIS FeatureServer / MapServer endpoints;
- Socrata open-data endpoints;
- city open-data portals;
- county open-data portals;
- assessor/parcel GIS;
- contractor license records;
- business/entity records;
- public project pages;
- bid/procurement portals;
- public records portals;
- public crime context sources where appropriate and lawful.

## Lawful Acquisition Rule

ConstructionSight uses lawful public access routes only.

Allowed acquisition pathways include:

- official public APIs;
- official ArcGIS REST endpoints;
- official open-data portals;
- public CSV/JSON downloads;
- public PDF packets;
- public webpages;
- public search forms where access is permitted;
- user-provided authorized accounts when lawfully allowed and explicitly configured.

Prohibited or unsupported acquisition behavior includes:

- bypassing authentication;
- bypassing CAPTCHAs;
- exploiting private endpoints;
- credential misuse;
- ignoring legal/robots/access warnings;
- accessing non-public data without authorization.

## Source Registry Role

The source registry is the authoritative inventory of known sources.

Each source should track:

- source name;
- jurisdiction;
- operational region;
- platform family;
- public URL;
- access method;
- adapter family;
- legal access status;
- verification status;
- confidence score;
- refresh cadence;
- last checked timestamp;
- last successful refresh;
- last changed timestamp;
- last failure reason;
- expected data categories;
- coverage status;
- monitoring status.

## Coverage Status

Sources and discovered records should support coverage status values:

- `in_zone`;
- `adjacent_candidate`;
- `out_of_zone_reference`;
- `unknown_zone`;
- `unsupported`;
- `rejected`.

## Monitoring Status

Sources should support monitoring status values:

- `active`;
- `watchlist`;
- `reference_only`;
- `paused`;
- `failed`;
- `unsupported`;
- `needs_review`;
- `ignored`.

## Source Verification

Before a source becomes active, ConstructionSight should verify:

- URL reachability;
- platform family hints;
- public search availability;
- login requirement;
- CAPTCHA/access-friction indicators;
- permit/planning/document visibility;
- downloadable or queryable records;
- field availability;
- confidence score;
- source limitations.

Verification results should be persisted, listable, exportable, checksummed, and independently verifiable.

## Refresh Cadence

Refresh cadence should depend on source value, update frequency, and operational priority.

Suggested cadences:

- high-value active permit portals: frequent polling;
- active planning/permit open-data APIs: frequent or hourly polling;
- planning commission agenda sources: daily;
- CEQA/State Clearinghouse: daily;
- assessor/parcel sources: slower periodic refresh;
- contractor license/business entity sources: daily or weekly;
- crime context sources: daily or source-dependent, visually off by default;
- out-of-zone references: no active refresh unless promoted.

## Startup Pulse Orchestration

On startup, ConstructionSight should:

1. load cached operational-zone graph data immediately;
2. display source freshness and last update state;
3. start background refresh jobs for active in-zone sources;
4. detect new or changed records;
5. normalize and enrich those records;
6. update project clusters;
7. update relationship assertions;
8. update authority state;
9. emit graph update events;
10. stream UI updates into the map and panels.

The application should not open as an empty search-only tool. It should immediately show the regional construction pulse from cached and refreshed data.

## Delta Detection

The system should detect changes without treating every refresh as new information.

Delta detection should consider:

- source record identifiers;
- URL changes;
- status changes;
- permit issued/final/expired changes;
- new inspections;
- new documents;
- changed applicant/contractor/owner fields;
- new related records;
- changed valuation;
- changed project description;
- content hashes;
- timestamp changes.

## Enrichment Target Selection

Not every record deserves the same enrichment effort. The system should prioritize enrichment targets.

High-priority enrichment targets:

- new project clusters;
- projects with unknown authority;
- projects with known GC but unknown developer/director;
- high-value permits;
- major-project candidates;
- active construction phase signals;
- records tied to known high-value entities;
- user-selected search targets;
- relationship conflicts;
- stale high-value projects.

Lower-priority targets:

- likely standalone minor permits;
- duplicate confirmations;
- unchanged low-value records;
- stale out-of-zone references.

## Enrichment Status

Each enrichment target should support status values:

- `not_started`;
- `queued`;
- `in_progress`;
- `partially_enriched`;
- `enriched`;
- `failed`;
- `blocked`;
- `stale`;
- `needs_review`.

## Enrichment Failure Reasons

Failures should be explicit and actionable.

Failure reasons may include:

- source unavailable;
- timeout;
- portal changed;
- unsupported platform;
- login required;
- CAPTCHA/access friction detected;
- no public machine-readable path found;
- no results found;
- insufficient identifiers;
- conflicting candidates;
- parser failed;
- normalization failed;
- entity resolution ambiguous;
- legal access unavailable;
- rate limited;
- human review required.

## Search-Driven Enrichment

Search is a targeted enrichment trigger, not the only way data appears.

A user search may target:

- GC;
- developer;
- director;
- owner;
- applicant;
- address;
- APN;
- project name;
- permit number;
- CEQA/SCH number;
- jurisdiction;
- trade scope;
- opportunity type.

Search should:

1. load known graph data for the target;
2. search source registry and indexed records;
3. queue targeted enrichment jobs;
4. expand related entity/project relationships;
5. distinguish in-zone data from relationship-horizon references;
6. stream newly discovered relationships to the UI;
7. explain unresolved or missing data.

## Coverage Expansion

Coverage expansion should be governed.

Out-of-zone discoveries do not automatically become active monitoring sources.

Promotion path:

1. `out_of_zone_reference`;
2. `adjacent_candidate`;
3. `watchlist`;
4. `active`.

Promotion evidence may include:

- repeated in-zone entity activity in the outside jurisdiction;
- high-value project signals;
- commercial relevance;
- user decision;
- regional expansion plan;
- stable lawful public data source availability;
- source verification success.

## Relationship Horizon Integration

Out-of-zone references are preserved as entity footprint evidence but excluded from local pulse metrics by default.

They may appear in:

- GC profiles;
- developer profiles;
- director profiles;
- footprint summaries;
- expansion candidate panels;
- search results when relevant.

They should not clutter the default operational-zone map.

## Source Discovery Methods

Source discovery may use:

- jurisdiction website navigation;
- targeted public search queries;
- public GIS service discovery;
- agenda/staff report discovery;
- open-data catalog search;
- platform-family fingerprinting;
- source registry cross-checking;
- user-provided source hints;
- public documentation review.

Targeted search is allowed when focused on lawful public sources and access paths.

## Source Health

Each active source should expose source health indicators:

- healthy;
- degraded;
- stale;
- failing;
- blocked;
- unsupported;
- needs review.

The UI should show:

- last checked;
- last success;
- last change;
- last failure reason;
- next scheduled check;
- source confidence;
- adapter status.

## Event Integration

Source discovery and enrichment should emit events such as:

- `source_discovered`;
- `source_verified`;
- `source_verification_failed`;
- `source_refresh_started`;
- `source_refresh_completed`;
- `source_refresh_failed`;
- `source_changed`;
- `record_discovered`;
- `record_changed`;
- `enrichment_queued`;
- `enrichment_started`;
- `enrichment_completed`;
- `enrichment_failed`;
- `coverage_candidate_created`;
- `coverage_promoted`;
- `coverage_rejected`.

## Regional Pulse Integration

Regional pulse should aggregate active operational-zone data only by default.

Pulse outputs may include:

- active project clusters;
- new raw records;
- new or updated project clusters;
- phase changes;
- projects with known GC;
- projects with unknown authority;
- high-value project candidates;
- source health warnings;
- enrichment backlog;
- recently resolved authority;
- recently discovered relationships.

## Non-Negotiable Constraints

- Do not let source discovery trigger uncontrolled crawling.
- Do not promote out-of-zone references automatically.
- Do not hide enrichment failures.
- Do not treat no result as no activity without explaining source coverage.
- Do not bypass access controls.
- Do not pollute the local pulse with out-of-zone references.
- Do not enrich high-value targets without preserving evidence and confidence.
- Do not allow stale data to appear fresh.

## Product Meaning

This model is the operating layer that keeps ConstructionSight alive. It governs how public sources are found, verified, refreshed, enriched, promoted, rejected, and explained so the live construction pulse and relationship graph remain current, lawful, evidence-backed, and geographically controlled.
