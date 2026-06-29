# Parcel Source Schema Preview

The parcel source registry says which sources are targets. The schema preview says whether a source or file is understandable enough to proceed to import preview.

This is still not live parcel import. It is a safety gate.

## Core rule

Do not import parcel records until the source schema has been inspected, mapped, and scored.

A parcel source can be high priority while still being unsafe for import. ConstructionSight must first answer:

```text
What fields exist?
Which fields map to APN, county, address, owner, zoning, land use, geometry, and updated-at?
Is geometry available?
Is the spatial reference known?
Are required roles missing?
Which fields need manual mapping?
```

## Required first-pass roles

The first schema preview requires:

- APN
- county

Additional high-value roles include:

- address
- owner
- jurisdiction
- zoning
- land use
- acreage
- centroid latitude
- centroid longitude
- geometry
- source record ID
- updated timestamp

## Preview statuses

Schema preview results can be:

- `ready_for_import_preview`
- `needs_mapping`
- `missing_required_fields`
- `unsupported`

A source with missing APN or county cannot proceed to import preview without manual mapping or a better source.

## Supported first inputs

The first implementation supports:

- registered parcel source expected mappings
- JSON schema-preview fixtures
- Regrid-like schema fields
- county GIS / ArcGIS-style field names
- user-provided CSV/GeoJSON field lists

## CLI

```bash
constructionsight-parcel-sources preview-schema --source-key regrid:licensed-parcel-provider
constructionsight-parcel-sources preview-schema --input schema-preview.json --json-output
```

The command emits table output or deterministic JSON. File output requires `--json-output`.

## Why this matters

The next phase is parcel import preview. That phase should never guess which column is APN or whether geometry is trustworthy. Schema preview creates the contract needed before importing county files, Regrid-style exports, ArcGIS metadata, or user-provided parcel data.
