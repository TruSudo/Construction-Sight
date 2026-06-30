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
- GeoJSON point/polygon/multipolygon coordinate extraction
- coordinate-average centroid
- envelope calculation
- geometry hash
- spatial-reference preservation
- limitations for unparsed geometry or unverified spatial reference

No external GIS dependency is required in this phase. More exact topology and projection behavior can be added later.

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

After this layer lands, the next phase is site resolver enrichment from parcel records: APN/address/coordinate hints should be matched against parcel core records with reasons, confidence, and limitations.
