# Parcel Source Registry

The parcel/site resolver creates deterministic site keys from APNs, addresses, coordinates, geometry hints, jurisdictions, and counties. The next layer is a provider-neutral source registry that says where parcel data can come from, what lawful boundary applies, what fields are expected, and what work remains before import.

## Core rule

Do not pretend parcel coverage exists before the source endpoint and schema are verified.

The registry deliberately separates source targets from import-ready sources. A county GIS layer can be a high-priority target without being treated as verified coverage. Regrid can be a licensed provider target without becoming a hard dependency. User-provided exports can be supported without knowing their schema until preview.

As of the evidence snapshot observed on 2026-07-14, the official San Bernardino and Riverside county parcel endpoints and live schemas are verified for preview. Both layers advertise the primitives needed for a bounded ArcGIS proof, but their canonical acquisition assessments remain `metadata_only`. They are not import-ready: executed count and page proof, restart safety, exclusions, and countywide completeness remain unproven. The complete evidence, authority limits, and gap computation are documented in [parcel source verification and county coverage](parcel_source_verification.md); the advertised-versus-executed boundary is documented in [parcel ArcGIS acquisition gates](parcel_arcgis_acquisition.md).

## First-phase source types

The first registry supports:

- county GIS parcel targets
- city GIS parcel targets
- assessor exports
- licensed providers
- user-provided parcel files
- open-data portals

## Lawful boundaries

Every parcel source declares an access boundary:

- `open_public_data`
- `public_metadata_only`
- `lawful_api_or_license`
- `user_provided_file`
- `unsupported`

This keeps ConstructionSight from confusing a design target with permission to import data.

## Canonical field targets

The registry maps source fields toward canonical parcel roles:

- APN
- address
- owner
- county
- jurisdiction
- zoning
- land use
- acreage
- centroid latitude
- centroid longitude
- geometry
- source record ID
- updated timestamp

Unverified-source mappings remain targets. The two verified county profiles now use only fields observed in their official live schemas.

County-scoped services do not need to fabricate physical `county` or `state` columns. `ParcelConstantFieldValue` records those values as source-scope constants with an evidence reference. Schema and row preview treat verified constants as available roles while keeping them visibly distinct from source fields.

## Verified county preview boundary

| Source | Access | Format | Observed canonical fields | Known omissions or limits |
|---|---|---|---|---|
| San Bernardino County parcel polygons | Open public data | ArcGIS Feature Service | APN, owner, jurisdiction, zoning, acreage, geometry, source record ID; county/state constants | No situs-address field; owner is not legal-title proof; 1,000-record service limit |
| Riverside County PARCELS_CREST | Open public data | ArcGIS Map Service layer | APN, situs street, situs city, acreage, geometry, source record ID; county/state constants | No owner field in the current live field list; assessment class is not planning land use; right-of-way and river polygons excluded; 2,000-record service limit |

The registry assigns no blanket authority. Verification profiles classify APN as authoritative only for the assessment-parcel identifier. Other supplied fields remain official evidence until proposition-specific authority is independently established.

## Why this comes before GIS ingestion

Parcel ingestion is dangerous if it starts with one-off scripts. Every county, city, export, and licensed provider can differ in field names, geometry support, update cadence, and restrictions. The registry creates a durable control surface before live import begins:

```text
parcel source target
  -> lawful boundary
  -> coverage metadata
  -> verified field mapping or explicit target mapping
  -> digest-bound official evidence
  -> field-specific verification profile
  -> county coverage-gap report
  -> preview readiness
  -> import readiness
  -> site-resolution enrichment
```

## Phase path

The intended next phases are:

```text
parcel source registry
  -> digest-bound metadata snapshot
  -> bounded count, adjacent-page, and exact-replay verification
  -> count-reconciled complete acquisition rehearsal
  -> open county parcel import preview
  -> geometry/centroid normalization
  -> site resolver enrichment from parcel records
  -> project/site graph linkage
```
