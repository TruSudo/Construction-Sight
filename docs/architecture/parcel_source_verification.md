# Parcel Source Verification and County Coverage

The parcel source registry owns provider identity, lawful access, source format, and canonical mappings. This layer binds those registry records to observed official evidence, turns verified profiles into parcel-assurance source contexts, and reports exactly what is still missing before countywide acquisition.

It is runtime governance, not a planning document.

## Evidence boundary

`ParcelSourceEvidence` is immutable and digest-bound. Its ID covers:

- source key and county;
- official public URL;
- evidence kind;
- observation time;
- observed facts;
- affected parcel fields; and
- limitations.

Changing any value invalidates the ID. Evidence statements and field roles are unique and canonically ordered.

The 2026-07-14 snapshot contains eight official observations covering:

- the San Bernardino County open-data dataset page;
- the San Bernardino ArcGIS parcel service ownership and maintenance metadata;
- the San Bernardino ArcGIS parcel feature layer and live field schema;
- the San Bernardino Assessor property-information limitations;
- the Riverside PARCELS_CREST portal entry;
- the Riverside live Assessor MapServer layer and field schema;
- Riverside GIS data-distribution accuracy limitations; and
- Riverside Assessor parcel-map scope.

## Verification profiles

`ParcelSourceVerificationProfile` binds one registry source to its evidence IDs, schema fields, mappings, geographic constants, access boundary, source format, spatial reference, maximum record count, lineage, authority, and unresolved limitations.

A `verified_preview` profile requires both public-access proof and schema proof. It does not imply:

- a successful full-count query;
- correct pagination across the county;
- complete jurisdiction or parcel-type coverage;
- import retry/resume safety;
- source-schema stability;
- legal title;
- a surveyed boundary; or
- authoritative planning, zoning, ownership, tax, or land-use facts.

The two initial profiles remain `ready_for_preview`. `ready_for_import` is model-invalid unless both countywide record coverage and bulk acquisition have been verified. The [ArcGIS acquisition gates](parcel_arcgis_acquisition.md) now preserve advertised metadata, executed bounded queries, and complete rehearsal evidence as separate maturity stages; they never promote a profile automatically.

The exact schema reconciliation removes a stale synthetic `Shape` attribute from the San Bernardino profile and adds Riverside's observed `LAND` and `STRUCTURES` attributes. The explicit synthetic `geometry` role remains separate from live attribute fields.

## Proposition-specific authority

The verified profiles convert directly to `ParcelAssuranceSourceContext` objects. Their default authority is `official`, never `authoritative`.

APN is currently authoritative only as an assessment-parcel identifier. It is not proof of legal title or a surveyed boundary. Owner, zoning, acreage, address, and geometry remain official evidence until the office and proposition responsible for each fact have been independently established.

This preserves the assurance engine's existing rule: authority attaches to a field, not to a source as a whole.

## County coverage requirements

The default coverage report evaluates both target counties against:

- APN;
- address;
- owner;
- county and state;
- jurisdiction;
- zoning;
- land use;
- acreage; and
- geometry.

Every fact is evaluated for availability, proposition-specific authority, and at least two independent source lineages. Countywide record completeness and bulk acquisition are separate requirements.

No opaque percentage or confidence score is emitted. Each shortfall is an explicit gap code with affected fields, source keys, explanation, and next action.

The current report is correctly `incomplete`:

- San Bernardino lacks address and land-use coverage in the verified parcel layer.
- Riverside lacks owner, jurisdiction, zoning, and planning land-use coverage in the verified parcel layer.
- Both counties lack authoritative support for fields other than APN.
- Both counties lack two-lineage corroboration for every required field.
- Neither county has proven countywide record completeness.
- Neither county has proven full paginated acquisition.

## Persistence and operator inspection

Three verification tables retain the evidence and derived controls:

- `parcel_source_evidence` uses exact idempotent replay;
- `parcel_source_verification_profiles` uses exact idempotent replay; and
- `parcel_county_coverage_reports` uses semantic idempotency, excluding only generation time from report identity.

Typed loaders revalidate digest identities and reject disagreement between indexed columns and preserved payloads.

The read-only upstream operator exposes:

- `parcel_source_evidence` with source-key and county filters;
- `parcel_source_verification` with status, source-key, and county filters; and
- `parcel_county_coverage` with a status filter.

The parcel-source CLI also exposes `evidence`, `verification`, and `coverage` commands. Separate acquisition commands expose metadata, bounded plans, readiness, and one explicit bounded live probe. No command mutates source maturity or authorizes countywide import.

## Backward compatibility

Existing parcel core records, longitudinal observations, current-selection reports, assurance reports, geometry behavior, and site resolution are unchanged. `constant_fields` defaults to empty for every existing or user-provided source. `arcgis_map_service` is an additive source-format value.

The bounded ArcGIS client, immutable observations, assessment state machine, complete-rehearsal manifest, persistence, and read-only operator exposure are implemented. Both sources currently remain `metadata_only`. The next safe phase is to execute and persist the four-request bounded proof for each county, then design a separately controlled complete rehearsal only after those observations pass.
