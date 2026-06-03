# Product Requirements — GUI Map Interface and Relationship Memory

## Status

This document records a core ConstructionSight product requirement for the future GUI and intelligence layer.

## Requirement Summary

ConstructionSight must include a refined map-based interface for San Bernardino County and Riverside County construction intelligence.

The map must show construction-related sites and their current inferred project state, including whether a jobsite is active, close to activation, early-stage, stalled, or completed.

The system must also maintain persistent memory of developers, general contractors, contractors, directors, and recurring construction entities operating within the two-county target region.

## Map Interface Requirements

The GUI must display:

- jobsite locations
- parcels and APNs where available
- project address and jurisdiction
- county: San Bernardino or Riverside
- project phase
- active, near-active, early-stage, inactive, completed, or stalled status
- CEQA, planning, grading, permit, and agenda milestones
- general contractor when known
- developer or owner entity when known
- applicant when known
- related public documents
- confidence level
- provenance and evidence trail

## Jobsite State Requirements

Initial state labels should include:

```text
early_signal
entitlement_in_progress
approved_not_issued
near_activation
active
inspection_stage
completed
stalled
unknown
```

These states should be derived from public-record signals including:

- CEQA document activity
- planning commission agenda items
- city council or board approvals
- tentative tract maps
- development agreements
- grading permits
- building permits
- permit issued status
- inspection records
- finaled permits

## Developer Section Requirements

The GUI must include a developer-focused section that stores and displays developer entities active in San Bernardino County and Riverside County.

Developer profiles should include:

- developer/entity name
- known aliases or related LLCs where evidence supports the connection
- active projects
- historical projects
- jurisdictions where active
- parcels/APNs linked to projects
- CEQA records linked to projects
- planning cases linked to projects
- permits linked to projects
- agenda items linked to projects
- known representatives or applicants where publicly disclosed
- confidence and provenance for each relationship

## General Contractor Section Requirements

The GUI must include a general-contractor-focused section that stores and displays general contractors active in San Bernardino County and Riverside County.

General contractor profiles should include:

- contractor business name
- contractor license number when publicly available
- license classification when available
- active projects
- historical projects
- jurisdictions where active
- permits linked to contractor
- site addresses linked to contractor
- developer/owner relationships where publicly supported
- project type patterns
- confidence and provenance for each relationship

## Relationship Memory Requirements

ConstructionSight must maintain persistent relationship memory between entities and projects.

The relationship memory must support links between:

- developers and projects
- general contractors and projects
- applicants and projects
- owners and parcels
- contractors and permits
- CEQA records and projects
- planning cases and projects
- agenda items and projects
- documents and projects
- sites and permits
- sites and planning cases

Each relationship must preserve:

- relationship type
- subject entity/key
- object entity/key
- confidence score
- provenance/evidence
- source name
- source URL when available
- notes

## Existing Backend Alignment

The current backend foundation already supports this direction through:

```text
Site
Entity
PermitRecord
PlanningCaseRecord
CeqaRecord
AgendaItemRecord
DocumentRecord
RelationshipRecord
```

and through persistence tables:

```text
domain_sites
domain_entities
domain_permits
domain_planning_cases
domain_ceqa_records
domain_agenda_items
domain_documents
domain_relationships
```

## Future GUI Views

The GUI should eventually include:

1. Map View
2. Jobsite Detail View
3. Developer Directory
4. General Contractor Directory
5. Entity Profile View
6. Relationship Graph View
7. County/Jurisdiction Filter View
8. Active/Near-Active Project Queue
9. Evidence/Provenance Inspector
10. Export/CRM Lead Queue

## Non-Negotiable Integrity Rule

No developer, general contractor, owner, applicant, or relationship may be asserted as fact without stored provenance.

The system must distinguish:

- verified fact
- public-record text
- normalized inference
- probabilistic relationship
- unresolved ambiguity

## Implementation Timing

This requirement affects multiple phases:

- Phase 6 live adapters must populate sites, entities, documents, and relationships.
- Phase 7 intelligence scoring must classify project activity states.
- Phase 8 GUI must expose map, developer, GC, jobsite, and relationship views.
- Phase 9 packaging must include desktop application behavior, icon, and installer support.

## Completion Standard

This requirement is not complete until ConstructionSight can visually display active and near-active jobsites on a map, show associated developers and general contractors, and preserve searchable relationship memory across San Bernardino County and Riverside County public-record data.
