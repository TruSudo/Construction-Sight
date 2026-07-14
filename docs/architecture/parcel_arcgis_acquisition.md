# Parcel ArcGIS Acquisition Gates

The ArcGIS acquisition layer turns official service metadata and deliberately bounded read-only requests into durable evidence. It does not treat an advertised capability, a successful sample, or one complete rehearsal as interchangeable facts.

This layer is an additive control surface between parcel-source verification and any countywide import.

## Proof ladder

| Status | Required evidence | What it authorizes |
|---|---|---|
| `metadata_only` | An exact, digest-bound layer metadata snapshot | A bounded probe plan only |
| `bounded_query_verified` | Count, first-page, adjacent-page, and exact first-page replay observations against the same schema snapshot | Design and review of a complete rehearsal; never a bulk production run |
| `bulk_rehearsal_verified` | Bounded proof plus a complete, count-reconciled, duplicate-free, restart- and retry-tested rehearsal manifest | Eligibility for a separate verification-profile promotion review |
| `blocked` | Capability, schema, sequence, replay, or scope disagreement | No advancement; investigate and create new evidence |

No status automatically changes a parcel verification profile. `ready_for_import` remains invalid until an explicit later promotion consumes the complete proof chain and independently establishes countywide record coverage.

## Metadata truth

`ParcelArcGISCapabilitySnapshot` binds:

- the exact verification profile and source scope;
- observation time, service version, geometry type, and spatial reference;
- type-aware field definitions and a schema fingerprint;
- the digest of the retained metadata projection;
- object-ID identity and advertised uniqueness;
- maximum record count;
- advertised query, count, ordering, and pagination behavior; and
- supported response formats and limitations.

Metadata parsing fails closed if the field set or maximum record count disagrees with the verification profile. Rendering, editing, and other mutable service properties are outside the canonical projection.

An advertised flag is not execution proof. It only allows ConstructionSight to construct a safe probe.

## Bounded probe

Every `ParcelArcGISProbePlan` contains exactly four requests, in this order:

1. a `returnCountOnly` request for `where=1=1`;
2. an object-ID-only page at offset zero;
3. the adjacent object-ID-only page; and
4. an exact replay of the first page.

Page requests are ordered by the unique object-ID field, return no geometry, and are limited to at most 100 identifiers. A plan is model-invalid if `bulk_run_authorized` is true.

The live CLI command is explicitly operator-invoked:

```text
constructionsight-parcel-sources acquisition-probe \
  --source-key san-bernardino:county-gis-parcels \
  --sample-size 2 \
  --json-output
```

The executor refreshes official layer metadata before sending the four planned queries. It requires HTTPS and exact HTTP 200 responses, refuses redirects, limits response size, retries only transient transport or HTTP failures under a fixed policy, and rejects service error payloads, malformed JSON, unexpected fields, unordered identifiers, schema drift, replay disagreement, and cross-source scope changes.

The bounded command does not write a county parcel dataset and cannot run a full acquisition.

## Executed proof

Each `ParcelArcGISProbeObservation` binds the exact planned request, observation time, retained canonical response JSON, independently recomputable response digest, schema fingerprint, and either:

- the reported total count; or
- the ordered object identifiers and transfer-limit flag returned by a page.

`bounded_query_verified` requires one observation for every planned request, byte-equivalent canonical first-page response replay, non-overlapping adjacent pages, an increasing combined identifier sequence, transfer-limit behavior consistent with the count, and a schema fingerprint matching the metadata snapshot.

Partial observations remain `metadata_only`. Contradictory observations become `blocked`; they are never averaged or silently discarded.

## Complete rehearsal manifest

`ParcelArcGISBulkManifest` is evidence for a separate controlled rehearsal, not a downloader. A valid manifest requires:

- identical start and end counts;
- retrieved, unique-ID, and reported counts to reconcile exactly;
- zero duplicate identifiers and zero failed pages;
- exactly one response digest per data page;
- the expected page count for the chosen page size;
- an observed terminal page;
- checkpoint-and-resume proof;
- bounded retry-recovery proof; and
- an object-ID-set digest.

Any failed invariant invalidates the manifest. A valid manifest advances the acquisition assessment only to `bulk_rehearsal_verified`; it still does not prove legal-title accuracy, surveyed geometry, proposition-specific authority, update freshness, parcel-type inclusion, or a production scheduler.

## Persistence and inspection

Five additive tables preserve the chain:

- `parcel_arcgis_capability_snapshots`;
- `parcel_arcgis_probe_plans`;
- `parcel_arcgis_probe_observations`;
- `parcel_arcgis_bulk_manifests`; and
- `parcel_arcgis_acquisition_assessments`.

Writes are dependency-ordered and immutable. Exact replays are idempotent; conflicting indexed fields, payload changes, missing parents, or a second observation for one request are rejected. One identical request may be shared by multiple bounded plans. Typed loads revalidate every digest and model invariant, and stored assessments are recomputed from their persisted snapshots, plans, observations, and optional manifests.

The read-only upstream operator exposes all five record kinds with source, county, and status filters. The parcel-source CLI exposes canonical metadata snapshots, bounded plans, current assessments, and the explicit live bounded probe command. The storage-summary CLI reports each new table independently.

## Current official boundary

The 2026-07-14 canonical snapshot records both official county layers as metadata-ready for a bounded probe:

| Source | Advertised page limit | Canonical state | Missing proof |
|---|---:|---|---|
| San Bernardino County parcel FeatureServer layer | 1,000 | `metadata_only` | Count, adjacent pages, replay, complete rehearsal |
| Riverside County Assessor MapServer layer | 2,000 | `metadata_only` | Count, adjacent pages, replay, complete rehearsal |

No live probe response or complete rehearsal is fabricated in the default objects. Neither source is bulk-authorized or import-ready.

The exact schema reconciliation also removes a stale synthetic `Shape` attribute from the San Bernardino profile and includes Riverside's observed `LAND` and `STRUCTURES` attributes. Geometry remains represented by the verification profile's explicit synthetic `geometry` role rather than an unobserved attribute name.

## Failure and recovery

Schema, object-ID, count, or pagination changes create a new metadata snapshot and block reuse of older proof. The operator must inspect the official service, update evidence and mappings if justified, and rerun the bounded chain.

If offset pagination proves unstable, a later acquisition implementation may use an official object-ID list followed by deterministic ID-batched queries, but it must preserve the same count reconciliation, uniqueness, response digests, checkpointing, retry evidence, and terminal-page guarantees. It cannot reinterpret a failed offset test as success.

## Compatibility

The new models, tables, commands, and operator record kinds are additive. Existing parcel records, observations, assurance reports, site resolution, source evidence, verification profiles, and county coverage reports retain their prior read and write contracts. Corrected default profile identities intentionally change because their schema content changed; previously persisted profiles remain immutable historical evidence.
