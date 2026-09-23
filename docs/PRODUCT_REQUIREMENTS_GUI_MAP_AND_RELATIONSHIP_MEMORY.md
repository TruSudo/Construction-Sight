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


## Future optional AI augmentation — non-blocking product requirement

ConstructionSight must remain **fully functional without an AI model, API key, networked
AI provider, or inference service**. AI is an optional enhancement to working,
deterministic acquisition, normalized persistence, evidence review, identity
resolution, geographic inspection, opportunity management, and commercial
workflows. The AI setting defaults to OFF and must not gate application startup,
source collection, database reads/writes, non-AI search, map rendering or ordinary
operator actions.

Once the non-AI operating baseline is demonstrated, add a replaceable model
adapter (local or explicitly configured remote provider) with explicit user
enablement, transparent model/provider selection, scope-limited inputs, rate/cost
limits, timeout/cancellation and graceful fallback. No raw source evidence,
personal/contact information, private lead notes or credentials may be sent to a
remote model without an explicit, reviewable disclosure/consent boundary. Never
send secrets in prompts. Retain model/version, prompt/template identity,
source-record revisions, response, timestamp and applicable user review with
each AI-generated artifact.

Potential opt-in uses: cite-backed dossier summaries, natural-language queries
over **already retained and permitted** source data, conflicting-record
explanations, candidate duplicate suggestions, follow-up research questions,
operator outreach/bid *drafts* from already approved records, and explanations
of existing map/entity findings. These are suggestions and derived analyses, not
source facts. Every factual assertion must resolve to inspectable retained
evidence; contradictory or missing evidence must be surfaced. AI must not invent
APNs, coordinates, construction stage, identities, contact details, approvals,
readiness scores or commercial numbers.

The model cannot directly mutate authoritative source records, bypass existing
authorization/effect-consumption controls, approve or transmit outreach, send
bids, approve payments, or change royalty balances. Human-reviewed suggestions
must pass the existing deterministic validation and explicit workflow
authorization before any permitted action. Model output is untrusted data:
defend against source-document prompt injection, expose uncertainty and
unsupported claims, and prohibit generated instructions from becoming
execution authority.

Acceptance must demonstrate that the same core tasks complete with AI disabled,
unavailable, timing out, or producing malformed/hostile output. Disablement must
restore the same deterministic application behavior without loss of records,
workflows or evidence. This requirement is recorded for future implementation;
it is **not an assertion that an AI integration exists today**.
