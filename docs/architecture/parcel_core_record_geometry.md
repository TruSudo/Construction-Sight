# Parcel Core Record and Geometry Normalization

Parcel row preview validates candidate rows. The parcel core record layer creates the first canonical parcel object ConstructionSight can safely use for site matching and graph linkage.

## Core rule

A parcel core record must preserve source identity, normalized APN, county, optional address, and optional normalized geometry. It must not silently treat malformed geometry, an unknown coordinate reference system, or a bounding envelope as trustworthy polygon proof.

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
- GeoJSON geometry, Feature, first-feature FeatureCollection, Point, Polygon, and MultiPolygon coordinate extraction
- coordinate-average centroid summaries
- envelope calculation
- geometry hash
- spatial-reference preservation
- limitations for unparsed geometry, unverified spatial reference, and polygon centroid approximation

Normalization stores the raw geometry and derived summary. It does not flatten Polygon or MultiPolygon evidence into the envelope for all later reasoning.

## Topology containment

The parcel topology layer can consume stored GeoJSON Polygon and MultiPolygon raw geometry for point containment when the spatial reference is explicitly recognized as longitude/latitude.

It preserves exterior rings, interior holes, boundaries, concavity, and separate multipolygon components. This prevents an envelope-only false positive when a point lies in empty space inside the bounding box but outside the actual parcel geometry.

Topology evaluation is used by parcel-backed site resolution. It is intentionally separate from the `ParcelGeometry` summary model so existing persisted parcel payloads remain readable and the raw source geometry remains the evidence input.

## Geometry hardening limits

Current polygon and multipolygon centroids are coordinate-average summaries, not area-weighted GIS centroids. Closed simple polygon rings have a redundant closing coordinate removed before the coordinate-average centroid is calculated, but centroid fields remain approximate.

Envelope fields are bounding-box summaries. They remain useful for indexed search and conservative fallback, but they are not used instead of valid Polygon/MultiPolygon topology.

Topology is currently limited to supported GeoJSON longitude/latitude geometry. The implementation does not yet:

- parse WKT Polygon or MultiPolygon geometry;
- transform arbitrary projected coordinate systems;
- calculate projection-aware area or distance;
- calculate area-weighted polygon/multipolygon centroids;
- repair malformed or self-intersecting topology; or
- claim survey-grade or legal parcel boundaries.

When topology cannot be justified, the site resolver may use the envelope only with explicit fallback limitations.

## Relationship to earlier gates

```text
parcel source registry
  -> parcel source schema preview
  -> parcel row preview
  -> parcel core record
  -> geometry normalization
  -> topology-aware site resolver enrichment
```

## Next phase

Remaining geometry work should prioritize projection-aware calculations and broader lawful geometry-format support. Any GIS dependency should be introduced only with explicit operational need, versioning, tests, and preservation of raw source geometry and limitations.
