# Parcel Source Registry

The parcel/site resolver creates deterministic site keys from APNs, addresses, coordinates, geometry hints, jurisdictions, and counties. The next layer is a provider-neutral source registry that says where parcel data can come from, what lawful boundary applies, what fields are expected, and what work remains before import.

## Core rule

Do not pretend parcel coverage exists before the source endpoint and schema are verified.

The registry deliberately separates source targets from import-ready sources. A county GIS layer can be a high-priority target without being treated as verified coverage. Regrid can be a licensed provider target without becoming a hard dependency. User-provided exports can be supported without knowing their schema until preview.

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

These mappings are targets, not proof that every source has every field.

## Why this comes before GIS ingestion

Parcel ingestion is dangerous if it starts with one-off scripts. Every county, city, export, and licensed provider can differ in field names, geometry support, update cadence, and restrictions. The registry creates a durable control surface before live import begins:

```text
parcel source target
  -> lawful boundary
  -> coverage metadata
  -> expected field mapping
  -> preview readiness
  -> import readiness
  -> site-resolution enrichment
```

## Phase path

The intended next phases are:

```text
parcel source registry
  -> open county parcel import preview
  -> geometry/centroid normalization
  -> site resolver enrichment from parcel records
  -> project/site graph linkage
```
