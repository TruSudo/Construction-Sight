# Parcel-Backed Site Resolution

Parcel-backed site resolution enriches the existing hint-only site resolver with canonical parcel core records.

## Core rule

A site should prefer a parcel-backed match when APN, address, or coordinate hints connect to a known parcel core record. If no parcel core record matches, ConstructionSight falls back to the existing source-neutral resolver and preserves the limitation.

Coordinate matching must use the strongest geometry method that can be justified by the stored evidence. A bounding envelope must not substitute for polygon topology when valid topology is available, and coordinates from an explicit projected CRS must not be compared directly to longitude/latitude hints.

## Matching signals

The implementation supports:

- exact normalized APN match
- exact normalized address match
- exact normalized point-geometry coordinate match
- coordinate coverage by verified GeoJSON or WKT/EWKT Polygon or MultiPolygon topology
- conservative envelope fallback when topology cannot be used and no explicit incompatible CRS is present
- refusal to compare explicit projected coordinates to longitude/latitude hints
- ambiguity preservation when multiple parcel records match equally
- fallback to hint-only resolution when no parcel record matches
- propagation of parcel and containment limitations into site-resolution candidates

## Scoring

```text
APN match: +70
address match: +20
coordinate match: +10
```

The coordinate score is unchanged across exact point, topology, and envelope-fallback methods. The reason and limitations distinguish the evidentiary strength of the method.

A single high-confidence parcel match resolves the site. Equal top-scoring parcel matches produce an ambiguous result.

## Topology containment

ConstructionSight performs dependency-free point-in-polygon checks when all of the following are true:

- the parcel geometry kind is Polygon or MultiPolygon;
- raw geometry is valid supported GeoJSON or WKT/EWKT;
- exterior and interior rings contain usable finite coordinate pairs;
- the coordinates fall within longitude/latitude bounds; and
- the spatial reference is explicitly recognized as longitude/latitude, currently EPSG:4326 or a recognized CRS84 form.

WKT/EWKT support includes Polygon, MultiPolygon, embedded SRIDs, and optional Z, M, or ZM dimensions. Extra dimensions are preserved in raw evidence but only the first two coordinates participate in planar point containment.

Topology evaluation preserves:

- concave polygon shape;
- exterior boundaries;
- interior holes;
- hole boundaries;
- multiple independent polygons in a MultiPolygon; and
- boundary coverage semantics.

A point that lies inside a polygon envelope but outside the actual polygon does not contribute a parcel-coordinate match. A point inside an interior hole does not match. A point on an exterior or hole boundary is treated as covered.

Successful topology matches use the reason:

```text
coordinate hint falls within parcel polygon topology
```

## Point geometry

A point parcel geometry matches only when the coordinate hint equals the normalized parcel point within the implementation's numeric tolerance. It does not treat a broad envelope as a point parcel.

Successful point matches use the reason:

```text
coordinate hint matches parcel point geometry
```

Point matching does not override an explicit incompatible CRS. Projected point coordinates remain preserved but are not compared to longitude/latitude hints until a governed transform exists.

## Envelope fallback

Envelope containment remains available when topology cannot be justified because:

- raw polygon geometry is absent;
- raw geometry cannot be parsed as supported GeoJSON or WKT/EWKT;
- the geometry type is unsupported by the topology engine; or
- the spatial reference is missing and the stored summary remains geographically plausible.

A successful fallback match uses the reason:

```text
coordinate hint falls within parcel envelope
```

The candidate must preserve `coordinate containment uses parcel envelope only` plus the specific reason topology was unavailable. Envelope fallback remains a candidate signal, not parcel-boundary proof.

An explicit non-longitude/latitude CRS is different from a missing CRS. It does not permit envelope fallback against latitude/longitude hints. The resolver returns no coordinate match and preserves:

```text
coordinate containment was not evaluated because the explicit spatial reference is not recognized as longitude/latitude
```

## Geometry limitation rule

Geometry limitations already stored on the parcel core record carry forward into the site-resolution candidate. Topology containment removes only the obsolete claim that a verified topology match was envelope-only. It does not remove centroid, projection, source-quality, topology-validity, or survey-grade limitations.

Topology is still not a legal boundary determination. ConstructionSight does not currently transform arbitrary coordinate reference systems, perform projection-aware distance or area calculations, repair invalid GIS topology, or validate all OGC polygon constraints.

## Why this matters

The parcel source registry, schema preview, row preview, and parcel core record layers are useful only if the site resolver can consume them without introducing false parcel matches.

```text
public record hints
  -> site-resolution input
  -> point / GeoJSON-or-WKT topology / limited envelope evaluation
  -> CRS compatibility gate
  -> parcel-backed site candidate
  -> opportunity/project graph anchor
```

## Remaining geometry work

Future work may add:

- governed coordinate-reference-system transformation;
- projection-aware or geodesic area and distance calculations;
- topology validity checking and repair for malformed or self-intersecting geometry;
- additional lawful geometry and collection types; and
- optional use of a vetted GIS library when operational requirements justify the dependency.
