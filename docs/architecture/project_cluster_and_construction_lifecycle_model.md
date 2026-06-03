# Project Cluster and Construction Lifecycle Model

## Status

Accepted design direction.

## Purpose

ConstructionSight must distinguish individual public records from real construction projects. A permit, planning case, CEQA record, agenda item, parcel record, or inspection record may be only one piece of a larger project. The platform must cluster related records into evidence-backed project objects and infer construction lifecycle state without pretending that a single permit proves the whole project.

This model defines how ConstructionSight should reason from fragmented public records toward project clusters, lifecycle phase, standalone activity, and major-project probability.

## Core Rule

A permit is an event record. A project is a cluster of related evidence.

ConstructionSight must not assume:

- one permit equals one project;
- one master permit contains all relevant records;
- one trade permit is always standalone;
- permit timing alone proves construction phase;
- every project has complete authority data in the first source checked.

## Public Record Types That May Contribute to a Project Cluster

A project cluster may be supported by records such as:

- permit records;
- permit detail pages;
- inspection records;
- planning applications;
- entitlement approvals;
- design review records;
- CEQA records;
- State Clearinghouse records;
- agenda items;
- staff reports;
- public hearing notices;
- parcel records;
- GIS features;
- assessor records;
- contractor license references;
- business/entity records;
- public project pages;
- public portfolio references;
- public bid/procurement records;
- public utility or right-of-way records.

## Project Cluster Entity

A `ProjectCluster` represents a probable or confirmed construction project assembled from one or more related public records.

A project cluster should support:

- stable project cluster identifier;
- project name when known;
- normalized address;
- APN or parcel identifiers;
- jurisdiction;
- geography/geometry;
- project type;
- lifecycle phase;
- cluster status;
- cluster confidence;
- major project probability;
- standalone permit probability;
- known authority roles;
- missing authority roles;
- related permits;
- related planning records;
- related CEQA records;
- related documents;
- source evidence;
- first seen timestamp;
- last seen timestamp;
- last updated timestamp.

## Cluster Evidence

Every cluster decision must preserve evidence.

Cluster evidence may include:

- same normalized address;
- same APN;
- same parcel geometry;
- same owner;
- same applicant;
- same general contractor;
- same developer;
- same project name;
- same planning case number;
- same permit group number;
- same master permit number;
- same CEQA/SCH number;
- same agenda/staff report reference;
- same legal description;
- same tract/subdivision reference;
- close date proximity;
- compatible permit sequence;
- compatible construction scope;
- shared document references;
- shared source URL patterns.

## Cluster Confidence

Project clusters should have confidence scores and statuses.

Suggested cluster statuses:

- `confirmed`: public source explicitly links records through project number, master permit, case number, or authoritative document;
- `probable`: multiple strong evidence signals support clustering;
- `possible`: limited evidence supports clustering but more enrichment is needed;
- `conflicting`: evidence supports more than one possible cluster or identity;
- `standalone`: record appears likely to be isolated activity;
- `rejected`: candidate cluster was rejected by rule or review;
- `needs_review`: automated confidence is insufficient.

## Standalone Activity vs Project Activity

A single permit may be:

- minor standalone activity;
- trade-specific opportunity;
- child permit in a larger project;
- deferred submittal;
- revision;
- after-the-fact compliance record;
- maintenance record;
- signal of a project phase.

ConstructionSight should estimate:

- `standalone_probability`;
- `major_project_probability`;
- `child_record_probability`;
- `phase_signal_strength`.

Example standalone-like records:

- water heater replacement;
- minor electrical repair;
- simple reroof;
- homeowner pool addition without related project evidence;
- isolated EV charger installation.

Example project-like records:

- grading plus building permit plus trade permits on same APN;
- planning case followed by building activity;
- CEQA notice followed by entitlement and permit records;
- multiple permits across the same project address within a narrow window;
- master permit with child trade permits;
- staff report naming developer plus later permit activity.

## Master Permit and Child Permit Rule

Some jurisdictions expose a master permit, parent permit, or project number. Others do not. ConstructionSight should use explicit source linkage where available, but it must not depend on it.

When explicit linkage exists, it should be high-confidence cluster evidence.

When explicit linkage does not exist, the system should infer relationships through APN, address, owner, applicant, GC, project name, source timing, and document references.

## Construction Lifecycle Phases

Suggested lifecycle phases:

- `unknown`;
- `conceptual_or_preapplication`;
- `planning_entitlement`;
- `environmental_review`;
- `approved_not_permitted`;
- `preconstruction`;
- `demolition`;
- `site_work_grading`;
- `foundation`;
- `vertical_construction`;
- `rough_in_trades`;
- `fire_life_safety`;
- `specialty_systems`;
- `inspection_finalization`;
- `completed_occupied`;
- `stalled_expired`;
- `cancelled_or_withdrawn`.

## Phase Evidence Rule

Permit timing is a strong phase signal, but not standalone proof.

Lifecycle phase should consider:

- record type;
- permit type;
- planning case status;
- CEQA status;
- application date;
- issued date;
- inspection date;
- final date;
- expiration date;
- project status;
- permit status;
- sequence of related permits;
- inspection activity;
- staff report language;
- source-specific status fields;
- contradiction evidence.

Interpretation examples:

- application date suggests intent or pipeline signal;
- issued date suggests authorization signal;
- inspection activity suggests active work signal;
- final date suggests completion signal;
- expiration suggests stalled or abandoned signal unless renewed;
- revisions suggest active design or construction change;
- deferred submittals often suggest child records inside a larger project.

## Phase Confidence

A project phase inference should include:

- phase value;
- confidence score;
- evidence records;
- evidence text;
- date basis;
- contradiction notes;
- last evaluated timestamp.

A phase should not silently overwrite older phase evidence. Phase history should be preserved.

## Cluster Timeline

Each project cluster should produce a timeline showing the sequence of public evidence.

Timeline events may include:

- source record discovered;
- planning application filed;
- CEQA record filed;
- agenda item heard;
- entitlement approved;
- permit applied;
- permit issued;
- inspection scheduled;
- inspection passed;
- revision filed;
- final inspection completed;
- certificate of occupancy issued;
- project cluster updated;
- authority relationship discovered.

## Boolean Scope Tags in Project Clusters

Boolean scope tags are scope signals, not proof of project importance.

Scope tags may include:

- `is_new_construction`;
- `is_addition`;
- `is_remodel`;
- `is_tenant_improvement`;
- `is_demolition`;
- `is_adu`;
- `is_multifamily`;
- `is_commercial`;
- `is_residential`;
- `is_public_works`;
- `is_ceqa_related`;
- `is_solar`;
- `is_battery_storage`;
- `is_ev_charger`;
- `is_hvac`;
- `is_heat_pump`;
- `is_roofing`;
- `is_electrical`;
- `is_plumbing`;
- `is_pool`;
- `is_fire_sprinkler`;
- `is_grading`;
- `is_concrete`.

Each scope tag should preserve:

- tag name;
- boolean value;
- confidence;
- evidence text;
- method;
- source record;
- timestamp.

## Relationship Graph Integration

A project cluster is the central object that links permits, parties, parcels, documents, lifecycle phase, and opportunity signals.

Relationship graph edges should commonly connect:

- developer to project cluster;
- owner to project cluster;
- director to project cluster;
- general contractor to project cluster;
- applicant to project cluster;
- architect to project cluster;
- engineer to project cluster;
- permit to project cluster;
- CEQA record to project cluster;
- planning case to project cluster;
- parcel to project cluster;
- jurisdiction to project cluster.

## Authority Enrichment Integration

Project clustering and authority enrichment must reinforce each other.

A cluster may begin with unknown authority, but every cluster should track:

- known authority roles;
- candidate authority roles;
- missing authority roles;
- unresolved authority reason;
- enrichment status;
- authority confidence by role.

If a project cluster exists, the system should be able to explain what record caused the system to know the project exists and what enrichment remains necessary.

## Regional Pulse Integration

The startup construction pulse should aggregate project clusters, not merely individual permits.

Pulse metrics should distinguish:

- number of new raw records;
- number of new project clusters;
- number of updated project clusters;
- number of active projects;
- number of standalone permits;
- number of major-project candidates;
- number of projects by phase;
- number of projects by jurisdiction;
- number of projects with known GC;
- number of projects with unknown authority.

## Real-Time Update Integration

Project clusters should update through graph update events.

Relevant update events include:

- `project_cluster_created`;
- `project_cluster_updated`;
- `permit_added_to_project`;
- `planning_case_added_to_project`;
- `ceqa_record_added_to_project`;
- `project_phase_changed`;
- `cluster_confidence_changed`;
- `standalone_probability_changed`;
- `major_project_probability_changed`;
- `authority_status_changed`.

## Non-Negotiable Constraints

- Do not treat a permit as a project without evidence.
- Do not infer phase from timing alone.
- Do not hide standalone probability.
- Do not hide major-project probability.
- Do not discard weak cluster candidates without preserving why.
- Do not merge records across addresses, APNs, or entities without evidence.
- Do not overwrite cluster history when a cluster changes.
- Do not present inferred clusters as confirmed unless explicit evidence supports confirmation.

## Product Meaning

The project cluster model is the bridge between raw public records and ConstructionSight's relationship intelligence. It turns scattered permits, planning cases, CEQA records, parcels, and documents into evidence-backed construction projects that can be mapped, enriched, searched, tracked, and explained.
