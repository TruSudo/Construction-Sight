# Coverage Boundary and Relationship Horizon Model

## Status

Accepted design decision.

## Purpose

ConstructionSight must distinguish between the geography it actively monitors and the wider footprint of entities discovered through relationship intelligence. General contractors, developers, directors, owners, applicants, architects, engineers, and related organizations may have projects outside the user's active operating area. Those out-of-zone relationships can be valuable context, but they must not cause uncontrolled source expansion or clutter the primary regional construction pulse.

## Core Rule

ConstructionSight separates:

- **Operational Zone**: the geography actively monitored by ConstructionSight.
- **Relationship Horizon**: out-of-zone projects, sites, jurisdictions, or relationships discovered because they connect to an in-zone entity.

Out-of-zone relationships may be recorded as entity footprint context, but they are not actively monitored by default.

## Operational Zone

The operational zone is the configured geography where ConstructionSight performs active source refresh, regional pulse aggregation, project clustering, relationship enrichment, and map population.

Initial operational zone:

- San Bernardino County, California.
- Riverside County, California.
- Cities and public sources within those counties as they are added to the source registry.

In-zone records are eligible for:

- automatic startup pulse aggregation;
- active source refresh;
- project clustering;
- entity resolution;
- relationship enrichment;
- map visibility by default;
- opportunity detection;
- phase inference;
- source health monitoring.

## Relationship Horizon

The relationship horizon captures out-of-zone information discovered because a known entity has a wider footprint.

Examples:

- A general contractor active in Riverside County is also discovered on a project in Phoenix.
- A developer active in San Bernardino County appears in an Orange County planning record.
- A director linked to an in-zone project is publicly associated with projects in another state.
- A GC's public portfolio reveals relevant historical projects outside the active monitoring region.

These records are useful as context for entity profiles, market footprint, relationship history, and expansion analysis. They must not automatically become part of the local construction pulse.

## Coverage Status Values

Every site, project, or discovered relationship should be classified with a coverage status.

- `in_zone`: fully inside the configured operational zone.
- `adjacent_candidate`: outside the operational zone but geographically or commercially relevant enough to consider for watchlist promotion.
- `out_of_zone_reference`: discovered through an entity relationship but not actively monitored.
- `unknown_zone`: location or jurisdiction is not sufficiently resolved.

## Monitoring Status Values

Every source, project, or relationship reference should have a monitoring status.

- `active`: actively refreshed and included in regional pulse logic.
- `watchlist`: monitored with limited cadence or pending operational-zone promotion.
- `reference_only`: stored as contextual footprint evidence but not refreshed automatically.
- `ignored`: intentionally excluded.
- `needs_review`: requires human or rule-based classification before monitoring is decided.

## Discovery Reason Values

Out-of-zone references must explain why they were recorded.

- `regional_pulse`: discovered through normal in-zone startup aggregation.
- `user_search`: discovered because the user searched for a specific entity, site, address, project, or jurisdiction.
- `connected_entity_enrichment`: discovered because it connects to an in-zone entity.
- `public_portfolio_reference`: discovered from a public company, contractor, developer, or project portfolio source.
- `related_document_reference`: discovered from an agenda packet, staff report, CEQA document, permit document, or other public record.
- `manual_import`: imported or entered by the user.

## Startup Visibility Rule

On startup, ConstructionSight should show the in-zone construction pulse by default.

Default startup behavior:

- show in-zone active and recently changed project clusters;
- show in-zone relationship updates;
- show source health for in-zone sources;
- hide out-of-zone references from the default map;
- exclude out-of-zone references from local pulse metrics;
- preserve out-of-zone references in entity profiles;
- allow a user-controlled toggle for outside-footprint visibility.

## Entity Profile Rule

Entity profiles may show out-of-zone references because they are relevant to understanding the entity's footprint.

A general contractor profile may show:

- in-zone active sites;
- in-zone historical sites;
- out-of-zone referenced projects;
- adjacent candidate jurisdictions;
- repeat developer/director relationships;
- last discovered date;
- monitoring status;
- evidence and confidence.

A developer or director profile may show the same footprint categories.

## Promotion Rule

Out-of-zone references do not automatically become active monitoring targets. They may be promoted only by explicit rule, user action, or future policy.

Promotion path:

1. `out_of_zone_reference`
2. `adjacent_candidate`
3. `watchlist`
4. `active`

Promotion should require evidence such as:

- repeated entity activity near the operational zone;
- commercially relevant jurisdiction;
- user selection;
- high-value project signals;
- frequent cross-jurisdiction relationships;
- strategic expansion plan.

## Map Behavior

The primary map is a relationship intelligence map focused on the operational zone.

Out-of-zone references should not clutter the default map. They should appear only when:

- the user opens a specific entity profile;
- the user enables an outside-footprint toggle;
- the user runs a targeted search involving that entity or jurisdiction;
- the reference is promoted to watchlist or active monitoring.

## Regional Pulse Rule

Regional pulse metrics are based only on active in-zone records unless a user explicitly changes the scope.

Out-of-zone references must not inflate:

- active local project counts;
- local permit counts;
- local GC activity counts;
- local developer activity counts;
- local opportunity counts;
- local phase-change counts.

They may appear in separate footprint metrics.

Example:

- In-zone active projects: 8.
- In-zone historical projects: 19.
- Out-of-zone referenced projects: 14.
- Expansion candidate jurisdictions: 3.

## Required Data Fields

Future models should support at least:

- `coverage_status`;
- `monitoring_status`;
- `discovery_reason`;
- `operational_region_id`;
- `jurisdiction_name`;
- `state`;
- `county`;
- `city`;
- `geometry_or_location_confidence`;
- `map_visibility_default`;
- `included_in_regional_pulse`;
- `first_seen`;
- `last_seen`;
- `last_checked`;
- `evidence_summary`;
- `confidence_score`.

## Non-Negotiable Constraints

- Do not let out-of-zone references silently expand source crawling.
- Do not include out-of-zone references in local pulse metrics by default.
- Do not clutter the default map with outside-footprint nodes.
- Do not discard out-of-zone relationships that explain an in-zone entity's footprint.
- Always label out-of-zone references clearly.
- Always preserve source evidence and confidence.

## Product Meaning

This model allows ConstructionSight to remain operationally focused while still building long-range relationship intelligence. The system can understand that a GC, developer, or director has a broader footprint without confusing that broader footprint with the user's current market pulse.
