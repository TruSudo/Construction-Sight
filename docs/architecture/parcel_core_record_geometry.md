# Parcel Core Record and Geometry Normalization

Parcel row preview validates candidate rows. The parcel core record layer creates the first canonical parcel object ConstructionSight can safely use for site matching and graph linkage.

Observation retention and current-record derivation are documented in [parcel longitudinal evidence](parcel_longitudinal_evidence.md). Field-level comparison of multiple current core records is documented in [parcel fact assurance](parcel_fact_assurance.md).

## Core rule

A parcel core record must preserve source identity, normalized APN, county, optional address, and optional normalized geometry. It must not silently treat malformed geometry, an unknown coordinate reference system, projected coordinates, or a bounding envelope as trustworthy longitude/latitude polygon proof.

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

- WKT and EWKT Point, Polygon, and MultiPolygon parsing
- optional WKT Z, M, and ZM dimensions while using the first two coordinates for planar topology
- embedded EWKT SRID preservation
- GeoJSON geometry, Feature, first-feature FeatureCollection, Point, Polygon, and MultiPolygon parsing
- exterior rings, interior holes, and independent multipolygon parts
- exterior-minus-hole, multipolygon-area-weighted centroid summaries
- envelope calculation for verified or plausibly geographic coordinates
- geometry hash
- spatial-reference preservation and conflict detection
- limitations for unparsed geometry, unverified or incompatible spatial reference, invalid effective area, unvalidated topology, and non-projection-aware centroid math

Normalization stores the raw geometry and derived summary. It does not flatten Polygon or MultiPolygon evidence into the envelope for all later reasoning.

## Area-weighted centroid summaries

Polygon centroids are derived with the planar shoelace formula. Interior-ring areas are subtracted from the exterior, and MultiPolygon centroids are weighted by each polygon's effective area.

The calculation is orientation-independent, removes a redundant closing coordinate, and preserves holes and separate polygon components. The resulting centroid is area-weighted in the source coordinate plane. It is not a geodesic centroid and is not projection-aware.

Every derived polygon or multipolygon centroid therefore retains:

```text
polygon centroid is area-weighted in the source coordinate plane, not projection-aware
```

The implementation does not currently validate ring self-intersections, hole placement, or full OGC polygon validity. Derived polygon geometry also retains:

```text
polygon topology has not been validated for self-intersections or hole placement
```

A zero or invalid effective area produces no centroid and an explicit limitation.

## Coordinate-reference-system boundary

Parsing and coordinate interpretation are separate decisions.

WKT/EWKT and GeoJSON topology may be recognized and preserved even when coordinates are projected. If an embedded or supplied CRS is explicitly non-geographic, ConstructionSight keeps the raw geometry, kind, hash, and CRS but does not write projected x/y values into latitude/longitude centroid or envelope fields.

If supplied and embedded CRS labels conflict, derived geographic summaries are blocked and the conflict is preserved as a limitation.

A geographic summary is produced only when:

- the explicit CRS is recognized as EPSG:4326 or a supported CRS84 form, or no CRS is supplied;
- coordinates are finite; and
- every summarized coordinate falls within longitude/latitude bounds.

Missing CRS remains an uncertainty and is not treated as verified. Explicitly projected CRS is not compared directly to longitude/latitude hints.

## Topology containment

The parcel topology layer consumes stored GeoJSON or WKT/EWKT Polygon and MultiPolygon raw geometry for point containment when the spatial reference is explicitly recognized as longitude/latitude.

It preserves exterior rings, interior holes, boundaries, concavity, and separate multipolygon components. This prevents an envelope-only false positive when a point lies in empty space inside the bounding box but outside the actual parcel geometry.

Topology evaluation is used by parcel-backed site resolution. It is intentionally separate from the `ParcelGeometry` summary model so existing persisted parcel payloads remain readable and the raw source geometry remains the evidence input.

## Geometry hardening limits

Envelope fields are bounding-box summaries. They remain useful for indexed search and conservative fallback, but they are not used instead of valid Polygon/MultiPolygon topology.

The implementation does not yet:

- transform arbitrary projected coordinate systems;
- calculate projection-aware or geodesic area and distance;
- repair malformed, self-intersecting, or otherwise invalid topology;
- validate that interior rings are properly contained and non-overlapping;
- handle every WKT collection or curve geometry type; or
- claim survey-grade or legal parcel boundaries.

When topology cannot be justified because raw geometry is missing or unparseable, the site resolver may use the envelope only with explicit fallback limitations. When an explicit CRS is incompatible with longitude/latitude hints, direct containment is not evaluated at all until a governed transform exists.

## Relationship to earlier gates

```text
parcel source registry
  -> parcel source schema preview
  -> parcel row preview
  -> parcel core record
  -> geometry normalization
  -> GeoJSON/WKT topology parsing
  -> topology-aware site resolver enrichment

parcel core observations
  -> immutable evidence retention
  -> conservative current selection and explicit supersession

governed current parcel core records + explicit source contexts
  -> field-level parcel claims
  -> dependency-aware assurance and conflict review
```

Parcel longitudinal evidence and assurance are additive. They retain and select canonical records without altering geometry normalization, topology, parcel identity, or site-resolution behavior.

## Next phase

Remaining geometry work should prioritize governed CRS transformation, projection-aware calculations, and topology validity checking. Any GIS dependency should be introduced only with explicit operational need, versioning, tests, and preservation of raw source geometry and limitations.
