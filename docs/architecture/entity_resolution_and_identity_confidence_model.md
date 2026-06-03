# Entity Resolution and Identity Confidence Model

## Status

Accepted design direction.

## Purpose

ConstructionSight must connect fragmented public records without collapsing distinct people, companies, projects, parcels, or sites into the same identity by mistake. Public construction data routinely contains spelling variants, abbreviations, punctuation differences, stale names, legal entity suffixes, aliases, and incomplete fields.

This model defines how ConstructionSight should normalize, compare, merge, separate, and explain identities across permits, planning records, CEQA records, agenda packets, GIS records, parcel records, contractor licenses, business entities, public portfolios, and other lawful public sources.

## Core Rule

Entity resolution is evidence-based and confidence-scored. Similar names are not enough.

ConstructionSight must distinguish:

- exact identity;
- normalized equivalent;
- probable same entity;
- possible same entity;
- related but distinct entity;
- conflicting identity;
- unresolved identity.

## Entity Types

Identity resolution should support at least:

- person;
- organization;
- developer;
- owner;
- applicant;
- general contractor;
- subcontractor;
- architect;
- engineer;
- director;
- project executive;
- project;
- site;
- parcel;
- permit;
- planning case;
- CEQA record;
- agency;
- jurisdiction;
- document;
- contact.

## Canonical Identity Fields

An entity should support:

- canonical entity identifier;
- entity type;
- canonical display name;
- normalized name;
- aliases;
- source names;
- identifiers;
- addresses;
- jurisdictions;
- related source records;
- confidence score;
- identity status;
- first seen timestamp;
- last seen timestamp;
- last verified timestamp;
- evidence summary;
- contradiction summary.

## Identity Status Values

Suggested identity statuses:

- `confirmed_same`: strong identifier or authoritative source confirms same identity;
- `probable_same`: multiple strong signals support same identity;
- `possible_same`: limited signals suggest same identity but more evidence is needed;
- `related_distinct`: entities are connected but should not be merged;
- `conflicting`: evidence conflicts or suggests possible false merge;
- `unresolved`: insufficient evidence;
- `rejected_match`: candidate match was rejected by rule or review;
- `superseded`: identity was merged into another canonical entity;
- `stale`: identity has not been verified recently.

## Normalization

Normalization helps compare records, but normalized sameness is not identity proof.

Name normalization may include:

- case folding;
- punctuation removal;
- whitespace normalization;
- legal suffix normalization;
- abbreviation expansion;
- common contractor naming variants;
- stopword reduction where safe;
- Unicode normalization.

Examples:

- `ABC Construction Inc.` → `abc construction`;
- `A.B.C. Construction` → `abc construction`;
- `D.R. Horton` → `dr horton`;
- `D R Horton Inc` → `dr horton`.

Normalization must preserve original source strings.

## Non-Negotiable Normalization Constraint

Do not normalize away distinctions that may be legally or operationally meaningful.

Examples:

- `ABC Construction` may not be the same as `ABC Construction Services`;
- `Smith Development LLC` may not be the same as `Smith Family Trust`;
- `123 Main St LLC` may not be the same as `123 Main Street Holdings LLC` without more evidence;
- a registered agent is not automatically the owner, developer, or project authority;
- a permit expeditor is not automatically the developer;
- an applicant is not automatically the GC.

## Strong Identity Signals

Strong signals may include:

- contractor license number;
- business registration identifier;
- parcel APN;
- permit number within a jurisdiction;
- planning case number;
- CEQA/SCH number;
- official project number;
- official master permit number;
- exact authoritative source linkage;
- public record explicitly saying entities are the same;
- same official address plus same authoritative identifier.

## Medium Identity Signals

Medium signals may include:

- same normalized name plus same address;
- same normalized name plus same phone or email where lawfully public;
- same normalized company name plus same contractor license class;
- same applicant name recurring on related project records;
- same project name plus same APN;
- same owner plus same project address;
- same GC plus same permit cluster;
- same developer in a staff report and project page.

## Weak Identity Signals

Weak signals may include:

- similar name only;
- same city only;
- same industry only;
- same legal suffix only;
- same first name/last name without role or context;
- same contractor trade category without identifier;
- shared keyword in project description.

Weak signals may create candidates. They should not merge entities by themselves.

## Negative Signals

Negative signals should reduce confidence or block merging.

Examples:

- different contractor license numbers;
- incompatible addresses;
- incompatible jurisdictions when no footprint evidence exists;
- different entity types;
- active conflicting names in authoritative sources;
- same name but different roles in unrelated contexts;
- owner LLC vs contractor company with no evidence of sameness;
- registered agent vs principal vs applicant confusion;
- person and organization name collision.

## Candidate Matching

The resolver should create candidate matches before merging.

Candidate match record should include:

- left entity;
- right entity;
- candidate score;
- matching signals;
- negative signals;
- source evidence;
- proposed status;
- explanation;
- created timestamp;
- review requirement.

## Merge Rule

Automatic merge should require strong evidence or multiple corroborating medium signals.

Suggested merge thresholds:

- `confirmed_same`: authoritative identifier or explicit source linkage;
- `probable_same`: high score with multiple independent signals and no strong negatives;
- `possible_same`: keep separate but linked as candidate;
- `related_distinct`: do not merge, preserve relationship edge;
- `conflicting`: do not merge, require review.

## Role-Sensitive Identity

The same name may appear in different roles. Role does not prove identity, but role context matters.

Examples:

- owner;
- applicant;
- developer;
- general contractor;
- subcontractor;
- architect;
- engineer;
- director;
- project executive;
- registered agent;
- consultant;
- permit expeditor.

Role-sensitive rule:

- applicant is not automatically developer;
- owner is not automatically developer;
- GC is not automatically developer;
- registered agent is not automatically project authority;
- consultant is not automatically decision-maker;
- repeated role association increases relationship confidence but does not alone confirm identity.

## Address Resolution

Addresses should be normalized separately from entities.

Address resolution should preserve:

- original source address;
- normalized address;
- parcel/APN linkage;
- geocoded point where available;
- address confidence;
- unit/suite information;
- jurisdiction;
- source-specific address format.

Address normalization must not collapse different units, parcels, or phases without evidence.

## Parcel Resolution

APN/parcel identifiers are strong signals but must be jurisdiction-scoped.

Parcel identity should include:

- APN;
- county;
- jurisdiction;
- geometry;
- site address;
- owner of record;
- effective date;
- source;
- confidence.

## Project Identity

Project names are often inconsistent. A project identity should not rely on name alone.

Project identity signals may include:

- project name;
- APN;
- address;
- planning case number;
- permit group;
- CEQA/SCH number;
- developer;
- owner;
- description;
- date window;
- staff report linkage.

## Relationship Graph Impact

Identity resolution directly affects the relationship graph. The graph must avoid both:

- fragmentation: one real entity split into many nodes;
- overmerge: distinct entities collapsed into one node.

Every merge or candidate link should preserve provenance and explain why it happened.

## Human Review

Certain identity decisions should require review:

- high-value project authority merge;
- person/entity ambiguity;
- conflicting source evidence;
- same name but different identifiers;
- uncertain director/project executive identity;
- role-sensitive promotion from applicant or agent to developer;
- out-of-zone relationship-horizon identity expansion.

## Audit Trail

Every identity action should be auditable.

Audit events may include:

- identity candidate created;
- identity candidate rejected;
- entities merged;
- merge reversed;
- alias added;
- canonical name changed;
- confidence changed;
- conflict detected;
- stale identity refreshed.

## Non-Negotiable Constraints

- Do not merge on name similarity alone.
- Do not discard original source strings.
- Do not hide candidate uncertainty.
- Do not treat normalized sameness as legal sameness.
- Do not equate registered agents, applicants, owners, developers, and GCs without role evidence.
- Do not overwrite identity history.
- Do not remove contradictory evidence.
- Do not let entity resolution silently alter project authority.

## Product Meaning

The entity resolution model keeps ConstructionSight's relationship graph trustworthy. It allows the platform to connect fragmented public construction records while preserving the difference between confirmed identity, probable identity, possible identity, related distinct entities, and unresolved ambiguity.
