# Opportunity Intelligence and Market Signal Model

## Status

Accepted design direction.

## Purpose

ConstructionSight must convert public construction records, project clusters, relationship intelligence, lifecycle phase signals, and contextual overlays into actionable market intelligence. The platform should help users understand not only what is being built, but why it matters commercially, who may be involved, when services may be relevant, and which opportunities deserve attention.

This model defines how ConstructionSight should represent construction-service opportunities, market signals, timing windows, confidence, evidence, and advertising context.

## Core Rule

An opportunity signal is an evidence-backed inference, not a guaranteed sale, need, risk, or outcome.

ConstructionSight may identify that a project appears relevant to a service category, but it must preserve:

- evidence;
- confidence;
- timing assumptions;
- source records;
- uncertainty;
- limitations;
- last update time.

## Opportunity Categories

ConstructionSight should support opportunity categories such as:

- construction site security;
- temporary fencing;
- surveillance trailers;
- lighting towers;
- access control;
- patrol services;
- roofing;
- solar installation;
- battery storage;
- EV charging;
- HVAC;
- heat pumps;
- electrical;
- plumbing;
- concrete;
- grading;
- demolition;
- fire sprinkler;
- fire alarm;
- tenant improvement;
- landscaping;
- signage;
- windows and doors;
- low voltage;
- general construction services;
- professional services where relevant.

## Market Signal Types

Market signals may include:

- new permit activity;
- new planning case activity;
- CEQA or environmental activity;
- project cluster creation;
- project phase change;
- major-project probability increase;
- high permit valuation;
- high project valuation;
- repeated GC/developer relationship;
- known developer entering new jurisdiction;
- known GC active on multiple sites;
- unknown authority needing enrichment;
- trade scope tag detected;
- inspection activity detected;
- stalled/expired project signal;
- crime context count near a site when toggled or requested;
- source freshness or coverage gap.

## Opportunity Signal Entity

An `OpportunitySignal` should represent a commercial or operational opportunity associated with a project cluster, site, entity, jurisdiction, or relationship.

It should support:

- opportunity identifier;
- category;
- project cluster reference;
- site reference;
- related entity references;
- geographic region;
- opportunity status;
- timing window;
- confidence score;
- evidence summary;
- source records;
- related scope tags;
- lifecycle phase basis;
- market context basis;
- limitations;
- first seen timestamp;
- last updated timestamp;
- expiration or stale timestamp.

## Opportunity Status Values

Suggested values:

- `candidate`;
- `active`;
- `high_priority`;
- `watchlist`;
- `stale`;
- `expired`;
- `rejected`;
- `needs_review`.

## Timing Window

Opportunities should include timing logic. A service may be relevant before, during, or after a project phase.

Suggested timing fields:

- `earliest_relevance_date`;
- `latest_relevance_date`;
- `phase_basis`;
- `timing_confidence`;
- `timing_evidence`;
- `stale_after`.

Examples:

- grading/site-work signals may be early indicators for security, fencing, and equipment monitoring;
- vertical construction may be relevant for security, trade services, access control, and surveillance;
- rough-in trade phase may be relevant for electrical, HVAC, plumbing, fire, and low-voltage services;
- final inspection may indicate late-stage or post-construction services;
- planning/entitlement may indicate future pipeline but not immediate jobsite needs.

## Security Opportunity Signals

Construction-site security opportunities may be supported by:

- active construction phase;
- grading/site-work phase;
- high-value project signal;
- multiple active permits;
- known GC or developer;
- equipment-intensive phase indicators;
- project footprint or large parcel;
- prior vandalism/theft/burglary/vehicle-theft context nearby, if crime context is toggled or requested;
- nighttime work or public right-of-way context where lawfully inferable;
- unknown site authority requiring further enrichment.

Security opportunity language must remain factual and contextual.

Allowed phrasing:

- public incident data shows nearby reported incidents;
- the project may be relevant to jobsite security planning;
- the site appears to be in an active construction phase;
- this is a candidate security opportunity based on public records.

Prohibited phrasing:

- this site will be targeted;
- this area is dangerous;
- this contractor needs security because crime is bad;
- this person or entity is associated with crime;
- predictive policing claims.

## Trade Opportunity Signals

Trade opportunities may be based on scope tags, permit type, lifecycle phase, and project cluster context.

Examples:

- `is_roofing` supports roofing opportunity;
- `is_solar` supports solar opportunity;
- `is_battery_storage` supports battery or electrical opportunity;
- `is_ev_charger` supports EV charging/electrical opportunity;
- `is_hvac` supports HVAC opportunity;
- `is_fire_sprinkler` supports fire protection opportunity;
- `is_grading` supports grading/concrete/site-work opportunity;
- `is_tenant_improvement` supports TI/vendor/service opportunity.

Scope tag presence is not enough by itself. The opportunity should consider phase, project value, status, geography, and recency.

## Relationship-Based Opportunity Signals

Relationship intelligence should help prioritize opportunities.

Examples:

- a GC has multiple active sites in the operational zone;
- a developer repeatedly uses the same GC;
- a director appears across several active projects;
- a known entity has a newly discovered in-zone project;
- a GC has out-of-zone footprint relevant to expansion analysis;
- a developer active outside the zone has entered the operational zone.

Relationship-based opportunities should show the supporting relationship evidence and confidence.

## Startup Pulse Integration

The startup regional pulse should aggregate opportunity signals without requiring a user search.

Startup opportunity metrics may include:

- active security opportunity candidates;
- new high-value project opportunities;
- projects entering construction phase;
- new trade-scope opportunities;
- new GC/developer relationship opportunities;
- projects with unknown authority requiring enrichment;
- opportunities by jurisdiction;
- opportunities by phase;
- opportunities by confidence tier;
- stale opportunities needing refresh.

## Search Integration

Search should generate targeted opportunity views.

Examples:

- search a GC to show all active opportunities tied to that GC;
- search a developer to show current and pipeline opportunities;
- search a jurisdiction to show market pulse and opportunities in that area;
- search a trade scope to show matching active and upcoming projects;
- search security opportunities to show active construction sites with relevant context.

## Crime Context Integration

Crime context is optional, off by default, and map/context-only unless requested.

When used for opportunity intelligence, crime context should be aggregated and factual:

- radius;
- time window;
- source;
- incident categories;
- incident counts;
- limitations.

Example:

`Public incident data shows 14 reported theft, burglary, vandalism, or vehicle-related incidents within 0.5 miles of this project site during the last 180 days.`

Crime context must not become a default relationship graph layer or an unsupported risk score.

## Confidence Model

Opportunity confidence should consider:

- project cluster confidence;
- lifecycle phase confidence;
- scope tag confidence;
- relationship confidence;
- data recency;
- source reliability;
- source coverage;
- contradiction evidence;
- missing authority;
- opportunity-specific rules.

Suggested confidence tiers:

- `high`: multiple corroborating signals and current project activity;
- `medium`: relevant signals but some missing information;
- `low`: weak or early-stage signal requiring enrichment;
- `unknown`: insufficient evidence.

## Evidence Requirements

Each opportunity should explain why it exists.

Evidence may include:

- permit number;
- permit type;
- permit status;
- planning case;
- CEQA record;
- project cluster;
- scope tags;
- phase inference;
- source URL;
- evidence text;
- incident count summary where applicable;
- relationship edge evidence;
- timestamps.

## Opportunity Expiration and Staleness

Opportunities should not live forever.

Staleness may be triggered by:

- project finaled;
- permit expired;
- no activity for configured time window;
- source unavailable for too long;
- phase advanced beyond relevance window;
- user rejection;
- contradictory evidence.

Stale opportunities should remain auditable but should not dominate active views.

## UI Implications

The UI should support:

- opportunity panel;
- opportunity filters;
- opportunity confidence tiers;
- opportunity category toggles;
- project/entity profile opportunity lists;
- startup opportunity pulse;
- exportable opportunity summaries;
- evidence drill-down;
- stale/active/watchlist filters.

Default view should prioritize active, in-zone, high-confidence, current opportunities.

## Export and Reporting

Opportunity exports should include:

- metadata envelope;
- schema version;
- generated timestamp;
- opportunity count;
- opportunity records;
- evidence;
- confidence;
- limitations;
- source references;
- integrity checksum.

Advertising/sales reports should preserve factual language and avoid unsupported claims.

## Non-Negotiable Constraints

- Do not present opportunity signals as guaranteed sales.
- Do not hide evidence or confidence.
- Do not use crime context as predictive policing.
- Do not overstate security risk.
- Do not keep stale opportunities active.
- Do not include out-of-zone references in local opportunity pulse unless explicitly requested.
- Do not infer service need from a single weak tag without context.
- Do not generate advertising claims unsupported by public evidence.

## Product Meaning

The opportunity intelligence model turns ConstructionSight from a passive construction data map into an actionable market intelligence platform. It helps users identify where construction activity, relationships, timing, and context create commercially relevant opportunities while preserving evidence, confidence, and responsible limitations.
