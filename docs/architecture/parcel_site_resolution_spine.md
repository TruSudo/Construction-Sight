# Parcel and Site Resolution Spine

Parcel identity is the land anchor for ConstructionSight.

A construction lead is not fully trustworthy until the project can be tied to a site: APN, address, coordinate, geometry, jurisdiction, county, or source record. Regrid-style parcel intelligence teaches that geometry is not just a map overlay; it is the stable object that connects public records to ownership, portfolio, zoning, buildings, permits, CEQA notices, agendas, inspections, contractors, and outreach territories.

## Core doctrine

```text
public record
  -> extracted site facts
  -> APN/address/coordinate/geometry normalization
  -> site-resolution candidate
  -> deterministic site key
  -> project/parcel graph anchor
```

The site key is not a claim of absolute ownership or verified parcel geometry. It is a deterministic resolution anchor with explicit reasons, limitations, conflicts, confidence score, and match strength.

## Supported first-phase signals

The first parcel/site resolver supports:

- APN normalization
- address normalization
- jurisdiction hints
- county hints
- coordinate hints embedded in intake facts
- deterministic `site:` keys
- conflict detection for multiple APNs or multiple addresses
- resolution status: resolved, partial, conflicting, unresolved
- match strength: exact, strong, moderate, weak, none

## Why this matters

Shovels-style permit intelligence becomes more powerful when permit records can join to parcel and property identities. Regrid-style parcel intelligence becomes more useful when parcel identity is connected to project movement. ConstructionSight must combine both:

```text
permit / CEQA / agenda / staff report / contractor signal
  -> site-resolution candidate
  -> parcel/site graph anchor
  -> transition event
  -> opportunity candidate
  -> outreach timing
```

## Conflict policy

The resolver does not silently collapse conflicting APNs or addresses. If a record contains multiple hard site identifiers, the result becomes `conflicting` and the conflict is preserved. Later parcel-provider adapters, county GIS layers, assessor data, or human review can resolve the discrepancy.

## Provider boundary

This spine is provider-neutral. Regrid can be a lawful licensed provider later, but the core resolver must also support open county parcel data, city GIS layers, assessor exports, CEQA records, permit systems, agenda packets, and user-provided files.

## Current implementation

The first implementation adds:

- `SiteIdentifier`
- `GeometryHint`
- `SiteResolutionInput`
- `SiteResolutionCandidate`
- `SiteResolutionResult`
- `resolve_site_from_intake`
- `constructionsight-site-resolution resolve-intake`

This establishes the land-anchor layer needed before building full parcel ingestion, geometry storage, GIS layers, owner/entity linkage, zoning enrichment, and project-to-parcel graph expansion.
