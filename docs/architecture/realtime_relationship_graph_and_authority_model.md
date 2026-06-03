# Real-Time Relationship Graph and Authority Model

## Status

Accepted design direction.

## Purpose

ConstructionSight is primarily a live construction relationship intelligence platform. Its core interface should not be a static permit map. It should be a real-time entity relationship graph over construction geography, showing who is building what, where, with whom, and what changed.

This model defines the foundation for directors, developers, owners, applicants, general contractors, projects, sites, parcels, permits, agencies, and related entities to be represented as evidence-backed graph nodes and edges.

## Core Product Rule

ConstructionSight's primary map is a relationship graph, not merely a permit pin map.

The platform should answer:

- who controls a project or site;
- which general contractor is working each site;
- which directors, developers, owners, applicants, and GCs repeatedly appear together;
- which projects are active, planned, stalled, enriched, or unknown;
- which relationships are confirmed, probable, possible, conflicting, or unresolved;
- what changed since the last refresh.

## Primary Graph Entities

The relationship graph should support at least:

- `Project`;
- `Site`;
- `Parcel`;
- `Permit`;
- `PlanningCase`;
- `CEQARecord`;
- `Developer`;
- `Owner`;
- `Applicant`;
- `Director`;
- `ProjectExecutive`;
- `GeneralContractor`;
- `Subcontractor`;
- `Architect`;
- `Engineer`;
- `Agency`;
- `Jurisdiction`;
- `Contact`;
- `SourceRecord`;
- `Document`.

## Primary Relationship Types

The graph should support at least:

- `developer_of`;
- `director_of`;
- `project_executive_for`;
- `owner_of`;
- `applicant_for`;
- `general_contractor_for`;
- `subcontractor_for`;
- `architect_for`;
- `engineer_for`;
- `permit_for`;
- `planning_case_for`;
- `ceqa_record_for`;
- `located_at`;
- `located_on_parcel`;
- `issued_by`;
- `reviewed_by`;
- `same_as`;
- `possibly_same_as`;
- `related_to`.

## Relationship Assertion Rule

A relationship is not merely a line on a map. It is an evidence-backed assertion.

Every graph relationship should support:

- subject entity;
- predicate / relationship type;
- object entity;
- relationship status;
- confidence score;
- evidence summary;
- supporting source records;
- contradictory source records if present;
- first seen timestamp;
- last seen timestamp;
- last verified timestamp;
- source family;
- jurisdiction;
- enrichment run identifier.

## Relationship Status Values

Relationships should not be treated as binary truth unless the evidence supports it.

Supported statuses:

- `confirmed`;
- `probable`;
- `possible`;
- `conflicting`;
- `unresolved`;
- `superseded`;
- `stale`.

## Site Authority Model

A site or project may have incomplete authority data. Missing authority is not a dead end. It is an enrichment state.

Authority roles may include:

- owner;
- developer;
- director;
- project executive;
- applicant;
- general contractor;
- architect;
- engineer;
- construction manager;
- site superintendent where lawfully and publicly available.

## Authority Status Values

A project or site should support a structured authority status.

- `not_started`: no authority enrichment has been attempted.
- `source_record_identified`: at least one source record explains why the site exists.
- `primary_parties_extracted`: owner, applicant, GC, or similar primary parties have been extracted.
- `related_records_searching`: related public records are being searched.
- `candidate_authorities_found`: one or more authority candidates exist but are not confirmed.
- `authority_partially_resolved`: some authority roles are confirmed or probable, but others remain unknown.
- `authority_confirmed`: required authority roles for current use case are confirmed.
- `conflicting_authority_candidates`: evidence points to conflicting candidates.
- `authority_unresolved_with_reason`: authority is unresolved and the reason is recorded.

## Unknown Authority Rule

ConstructionSight should not merely display `unknown` for site authority without a reason.

If authority is unknown, the system should explain why:

- `no_source_checked`;
- `current_source_lacks_party_fields`;
- `only_owner_llc_known`;
- `only_applicant_known`;
- `gc_known_authority_unknown`;
- `conflicting_candidates`;
- `source_access_unavailable`;
- `enrichment_failed`;
- `insufficient_confidence`;
- `human_review_required`.

## Construction Activity Evidence Rule

If ConstructionSight can reliably infer that a standing, active, or upcoming construction site exists, some public record or public evidence likely caused that inference. The system should preserve and pursue that evidence.

The system should ask:

- what source record caused us to know this site exists;
- which entities are present in that record;
- which fields are missing;
- which adjacent sources may contain the missing authority;
- which records share the same APN, address, project name, planning case, CEQA/SCH number, permit number, owner, applicant, GC, or geometry.

## Permit vs Project Rule

A permit is an event record. A project is a cluster of related records.

ConstructionSight must not assume:

- one permit equals one project;
- one master permit contains all project data;
- a trade permit is always standalone;
- permit timing alone proves construction phase.

The system should infer whether each permit is:

- standalone activity;
- a child permit;
- part of a larger project cluster;
- a revision or deferred submittal;
- a phase signal;
- a noise/minor maintenance record.

## Phase Signal Rule

Permit timing is a strong phase signal, but not standalone proof of construction phase.

Phase inference should consider:

- permit type;
- application date;
- issued date;
- inspection date;
- final date;
- status;
- related permits;
- planning records;
- CEQA records;
- project cluster evidence.

Suggested phase values:

- `planning_entitlement`;
- `environmental_review`;
- `preconstruction`;
- `site_work_grading`;
- `foundation`;
- `vertical_construction`;
- `rough_in_trades`;
- `fire_life_safety`;
- `specialty_systems`;
- `final_inspection`;
- `completed_occupied`;
- `stalled_expired`;
- `unknown`.

## Real-Time Enrichment Rule

The application should feel real-time. Public sources may not provide true push events, so ConstructionSight should provide near-real-time behavior through polling, delta detection, enrichment runs, event logs, and live UI updates.

Core flow:

1. source refresh or user search;
2. new or changed record detected;
3. normalization;
4. entity extraction;
5. entity resolution;
6. relationship candidate generation;
7. relationship assertion update;
8. project cluster update;
9. authority status update;
10. graph update event;
11. UI map and panel update.

## Graph Update Event Types

The system should support at least:

- `source_record_discovered`;
- `source_record_changed`;
- `entity_created`;
- `entity_merged`;
- `relationship_created`;
- `relationship_updated`;
- `relationship_confidence_changed`;
- `project_cluster_created`;
- `project_cluster_updated`;
- `authority_status_changed`;
- `project_phase_changed`;
- `permit_added_to_project`;
- `planning_case_added_to_project`;
- `ceqa_record_added_to_project`;
- `opportunity_signal_created`;
- `crime_context_updated`;
- `source_verification_added`;
- `export_created`.

## Graph Update Severity

Not all updates should visually dominate the map.

Suggested severity values:

- `high`: new project, new GC relationship, new director/developer relationship, authority resolved, major permit issued, phase changed;
- `medium`: new trade permit, inspection activity, status change, valuation signal, candidate authority found;
- `low`: duplicate confirmation, minor metadata update, source verification refresh, unchanged polling result.

## Startup Behavior

On startup, ConstructionSight should:

1. load the cached in-zone graph immediately;
2. show data freshness;
3. begin background refresh jobs;
4. stream graph updates as new data is processed;
5. preserve relationship-map focus;
6. keep crime context overlays off by default;
7. keep out-of-zone relationship-horizon references out of local pulse metrics by default.

The map should not open as an empty search box. It should show the regional construction pulse and relationship graph from cached and refreshed data.

## Search Behavior

Search is for targeted enrichment, not the only way data appears.

Search may target:

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

A search should expand and enrich the graph around the target, then stream new relationships into the UI.

## UI Implications

Primary UI views should include:

- relationship map;
- director/developer profile panel;
- GC profile panel;
- site/project panel;
- unknown authority panel;
- project timeline panel;
- live update feed;
- opportunity panel;
- optional crime context overlay controls.

Crime context is not a relationship graph layer by default. It is a toggleable contextual overlay.

## Non-Negotiable Constraints

- No relationship without evidence.
- No hidden certainty.
- No unresolved authority without a reason.
- No uncontrolled out-of-zone expansion.
- No default crime-overlay clutter.
- No treating a permit as a project without clustering evidence.
- No phase conclusion from timing alone.
- No real-time UI claim without data freshness and update provenance.

## Product Meaning

ConstructionSight turns fragmented public construction records into a live, evidence-backed relationship graph of who is building what, where, with whom, and what changed.
