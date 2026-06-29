# External Intelligence Capability Spine

ConstructionSight can lawfully study Shovels and Regrid at the capability level without cloning protected implementation details or taking licensed data. The goal is feature parity where lawful, and advantage where ConstructionSight can do better through evidence preservation, source snapshots, transition diffs, graph reasoning, and lead-timing intelligence.

## Operating boundary

This spine uses four evidence classes:

- public website claims
- public documentation claims
- user research from prior direct prompting and analysis
- ConstructionSight product doctrine

The direct Shovels/Regrid research is valuable and must not be flattened into generic marketing claims. It includes schema and architecture concepts such as permits, contractors, parcels, properties, addresses, residents, employees, universal person, decisions, Overture Places, `CONTRACTOR_GROUP_ID`, `IS_REPRESENTATIVE`, `PERSON_ID`, `ADDRESS_ID`, `FIRST_SEEN_DATE`, and Shovels/Regrid parcel joins. Those concepts guide ConstructionSight design, but the implementation must remain lawful and source-backed.

## Locked Shovels lessons

The important lesson is not simply that Shovels aggregates permits. The important lesson is that Shovels behaves like a normalized entity graph:

```text
permit -> address -> parcel -> property
permit -> contractor -> contractor group -> employee/person
permit -> decision/status history
owner/applicant/contact fields -> outreach candidates
first_seen/status/value/license/date changes -> movement signals
```

ConstructionSight should use this as a conceptual target while improving the lead-generation layer:

```text
source evidence
  -> preserved snapshot
  -> normalized record
  -> identity resolution
  -> field diff
  -> transition event
  -> opportunity candidate
  -> project graph
  -> lead score
  -> outreach preview
  -> audit trail
```

## Locked Regrid lessons

Regrid is the parcel backbone. Parcel geometry is not just a map feature; it is the stable identity object for construction intelligence:

```text
geometry -> canonical parcel -> owner -> portfolio -> assembly -> development activity
```

ConstructionSight must support APN, address, coordinate, centroid, geometry, polygon, jurisdiction, county, zoning, ownership, building footprint, and secondary-address pivots. Regrid can be a lawful licensed provider, but the system must also support open county parcel sources and conflicts between parcel sources.

## Advantage target

Shovels and Regrid provide powerful data infrastructure. ConstructionSight should outperform for site-security sales by optimizing around the actionable moment:

- new public source record observed
- CEQA or environmental-review movement
- planning/council/board decision movement
- permit application movement
- permit issuance
- contractor identified
- valuation changed
- inspection movement
- expiration/finalization
- parcel or address anchor confirmed
- contact channel discovered

A static database tells the user what exists. ConstructionSight should tell the user what changed, why it matters, who to contact, what evidence supports it, what is uncertain, and what to do next.

## Implementation layer

The first implementation is a capability registry and gap-report engine:

- `ExternalCapability` records Shovels/Regrid capability targets.
- `CapabilityReference` distinguishes public documentation from user research.
- `CapabilityGapReport` separates gaps, licensed blockers, and outperform targets.
- `constructionsight-external-intelligence` exposes the matrix and gap report for CLI/automation.

This is the durable planning layer before building individual adapters for Regrid-style parcel intake, Shovels-style permit/contractor graphing, source-change diffing, warehouse exports, GIS layers, and API/UI workflows.
