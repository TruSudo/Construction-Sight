# Evidence, Provenance, and Auditability Model

## Status

Accepted design direction.

## Purpose

ConstructionSight must be able to explain every important fact, inference, relationship, project cluster, authority conclusion, phase signal, opportunity signal, source verification result, and export. The platform's value depends on trustworthy public-record intelligence, not opaque conclusions.

This model defines how ConstructionSight should preserve source evidence, distinguish verified facts from inferred conclusions, maintain confidence and uncertainty, expose contradictions, and support audit-ready exports.

## Core Rule

No intelligence assertion without evidence.

ConstructionSight must preserve:

- what is claimed;
- whether it is fact, inference, candidate, or unresolved;
- what source supports it;
- what evidence text or field supports it;
- when it was observed;
- how it was derived;
- how confident the system is;
- what contradicts or limits it;
- whether it has changed over time.

## Assertion Types

The system should distinguish assertion types such as:

- `source_fact`: a directly observed field or fact from a public source;
- `normalized_fact`: a normalized version of a source fact;
- `identity_candidate`: a possible identity match;
- `identity_assertion`: an identity resolution conclusion;
- `relationship_candidate`: a possible relationship;
- `relationship_assertion`: a relationship conclusion;
- `project_cluster_candidate`: a possible project cluster;
- `project_cluster_assertion`: a cluster conclusion;
- `phase_inference`: a construction lifecycle conclusion;
- `authority_inference`: a project authority conclusion;
- `scope_tag`: a work-scope classification;
- `opportunity_signal`: a commercial or operational signal;
- `crime_context_summary`: an aggregated contextual incident summary;
- `source_verification`: a source verification result;
- `export_integrity_assertion`: an export checksum or verification result.

## Evidence Record

An `EvidenceRecord` should support:

- evidence identifier;
- source name;
- source URL;
- source family;
- jurisdiction;
- operational region;
- record type;
- source record identifier where available;
- retrieved timestamp;
- observed timestamp if source provides one;
- evidence field name;
- evidence value;
- evidence text excerpt;
- raw observation reference;
- content hash;
- retrieval method;
- access status;
- adapter name/version;
- confidence contribution;
- limitations.

## Source Fact vs Inference

ConstructionSight must separate source facts from system inferences.

Example source fact:

- Permit record lists `ABC Construction` in a contractor field.

Example inference:

- `ABC Construction` is probably the general contractor for the project cluster.

The inference may be high-confidence, but it is not the same thing as the raw source fact.

## Provenance Chain

Every important assertion should be traceable through a provenance chain.

Example:

1. raw source record retrieved from permit portal;
2. contractor field extracted;
3. contractor name normalized;
4. entity candidate generated;
5. entity resolved to canonical GC entity;
6. relationship candidate generated;
7. relationship asserted as `general_contractor_for`;
8. project cluster updated;
9. opportunity signal created;
10. export generated with checksum.

The system should be able to explain every step.

## Confidence Model

Confidence should be explicit and bounded.

Confidence may be influenced by:

- source reliability;
- source field specificity;
- identifier strength;
- corroborating sources;
- recency;
- contradiction evidence;
- normalization quality;
- entity resolution quality;
- relationship strength;
- project cluster confidence;
- phase inference confidence;
- opportunity-specific rules.

Suggested tiers:

- `high`;
- `medium`;
- `low`;
- `unknown`.

Numeric confidence may also be supported from 0 to 100.

## Confidence Constraint

A high-confidence inference must still disclose that it is an inference unless directly confirmed by a source.

Do not silently convert inference into fact.

## Contradiction Handling

ConstructionSight should preserve contradictions instead of overwriting them.

Contradictions may include:

- different owners listed across sources;
- different contractor names;
- conflicting project statuses;
- duplicate or divergent addresses;
- outdated vs current entity names;
- conflicting permit status;
- conflicting phase signals;
- identity resolution conflicts;
- relationship conflicts.

Contradiction records should support:

- conflicting assertion identifiers;
- source evidence on both sides;
- contradiction type;
- severity;
- resolution status;
- review requirement;
- timestamp.

## Time and Versioning

Facts and assertions may change over time. The system must preserve history.

Do not overwrite without history:

- source facts;
- entity names;
- relationship status;
- project phase;
- authority status;
- permit status;
- opportunity status;
- confidence values.

Every important update should create an audit event or version record.

## Audit Event Types

Suggested audit events:

- `source_record_retrieved`;
- `source_record_changed`;
- `source_verification_created`;
- `entity_candidate_created`;
- `entity_merged`;
- `entity_merge_rejected`;
- `relationship_candidate_created`;
- `relationship_asserted`;
- `relationship_changed`;
- `relationship_rejected`;
- `project_cluster_created`;
- `project_cluster_updated`;
- `phase_inferred`;
- `authority_status_changed`;
- `opportunity_signal_created`;
- `opportunity_signal_expired`;
- `contradiction_detected`;
- `human_review_required`;
- `export_created`;
- `export_verified`;
- `export_verification_failed`.

## Source Verification Auditability

Source verification results are audit records. They should remain listable, exportable, checksummed, and independently verifiable.

Verification results should preserve:

- source name;
- public URL;
- checked timestamp;
- URL reachability;
- platform detected;
- public search availability;
- login requirement;
- record visibility;
- confidence;
- notes;
- raw observations.

## Export Auditability

Exports should be self-describing and integrity-checkable.

Export payloads should support:

- metadata envelope;
- schema version;
- export type;
- generated timestamp;
- source application;
- record count;
- records;
- evidence references;
- confidence;
- limitations;
- integrity block;
- checksum algorithm;
- canonicalization method;
- payload scope;
- verifier compatibility.

## Advertising and Sales Claim Discipline

ConstructionSight may support advertising and sales context, but claims must remain evidence-bound.

Allowed:

- public incident data shows X reported incidents within Y radius during Z time window;
- public permit records indicate active construction activity;
- this project is a candidate opportunity based on public records;
- this relationship is inferred from permit and planning evidence.

Prohibited:

- unsupported claims that a site will be targeted;
- unsupported claims that a contractor needs a service;
- crime-based accusations against people or companies;
- hiding uncertainty in sales language;
- presenting inferred opportunity as guaranteed demand.

## User-Facing Explanation Requirement

For any project, relationship, authority conclusion, or opportunity, the user should be able to ask:

- why does the system believe this;
- what source records support it;
- how recent is the data;
- what confidence does it have;
- what is missing;
- what contradicts it;
- what changed since last time;
- can this be exported and verified.

The system should be able to answer.

## Non-Negotiable Constraints

- No unsupported assertions.
- No hidden inference.
- No lost source text.
- No overwritten history without audit trail.
- No ignored contradictions.
- No confidence score without evidence basis.
- No export without metadata and integrity path.
- No advertising claim without factual source basis.
- No treating public-record absence as proof of nonexistence without source coverage explanation.

## Product Meaning

The evidence, provenance, and auditability model makes ConstructionSight trustworthy. It allows users to rely on the platform not merely because it finds construction data, but because it can explain how it knows what it knows, what remains uncertain, and how the evidence can be verified later.
