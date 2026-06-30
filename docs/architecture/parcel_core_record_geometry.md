# Parcel Core Record and Geometry Normalization

Parcel row preview validates candidate rows. The parcel core record layer creates the first canonical parcel object ConstructionSight can safely use for site matching and graph linkage.

## Core rule

A parcel core record must preserve source identity, normalized APN, county, optional address, and optional normalized geometry. It must not silently treat malformed geometry as trustworthy.

## Parcel core record

The first core record includes:

- deterministic `parcel:` record ID
- source key
- source record ID
- APN
- normalized APN
- county
- state
- address
- normalized address
- jurisdiction
- zoning
- land use
- acreage
- optional geometry summary
- source-updated timestamp
- limitations

Ownership/contact enrichment is intentionally deferred. This phase establishes land identity first.

## Geometry normalization

The geometry layer supports:

- WKT point parsing
- GeoJSON geometry, feature, point, polygon, and multipolygon coordinate extraction
- coordinate-average centroid
- envelope calculation
- geometry hash
- spatial-reference preservation
- limitations for unparsed geometry, unverified spatial reference, and polygon centroid approximation

No external GIS dependency is required in this phase. More exact topology, area-weighted centroids, coordinate projection, and point-in-polygon behavior can be added later.

## Geometry hardening limits

Current polygon and multipolygon centroids are coordinate-average summaries, not area-weighted GIS centroids. Closed simple polygon rings have a redundant closing coordinate removed before the coordinate-average centroid is calculated, but this is still not survey-grade parcel topology.

Envelope fields are bounding-box summaries. They are useful for coarse candidate matching and indexed search, not legal boundary determinations.

## Relationship to earlier gates

```text
parcel source registry
  -> parcel source schema preview
  -> parcel row preview
  -> parcel core record
  -> geometry normalization
  -> site resolver enrichment
```

## Next phase

Future geometry work may add topology-grade containment and projection-aware calculations. Until then, every polygon-derived coordinate match must preserve its limitations.
