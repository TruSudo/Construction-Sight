# Shovels/Regrid Gap Alignment

Deep competitive research confirms that Shovels and Regrid should not be treated as one category.

Regrid is the parcel and geometry substrate: stable parcel identity, parcel paths, schema endpoints, GeoJSON parcel responses, tiles, feature service, batch point lookup, bulk delivery, zoning, ownership, matched buildings, matched secondary addresses, and roadway add-ons.

Shovels is the construction-activity overlay: permits, permit status/lifecycle fields, contractor search, contractor employees, contractor metrics, address search, residents, government decisions, release metadata, coverage metadata, GIS/CLI/API access, and warehouse delivery.

ConstructionSight should align to both without cloning either implementation.

## Alignment doctrine

```text
Regrid-style parcel spine
  -> ParcelRecord
  -> geometry normalization
  -> site resolver enrichment
  -> project/site graph

Shovels-style event and actor overlay
  -> PermitSnapshot
  -> PermitTransition
  -> ContractorIdentity
  -> DecisionRecord
  -> coverage/freshness checks

ConstructionSight-native advantage
  -> transition timing
  -> evidence-backed opportunity score
  -> outreach preview
  -> confidence and limitation transparency
```

## Highest-priority gaps

The current implementation path must answer these gaps first:

1. Parcel source schema preview
2. Parcel import preview
3. ParcelRecord and geometry normalization
4. Site resolver enrichment from parcels
5. PermitSnapshot and PermitTransition
6. Contractor identity and CSLB enrichment
7. DecisionRecord and decision-to-parcel matching
8. Opportunity enrichment from parcel, permit, contractor, and decision signals

## Why this matters

ConstructionSight does not need to become a national parcel vendor or generic permit warehouse first. The target product is narrower and stronger:

```text
Which parcel or project is moving?
What changed?
Who is connected?
What evidence proves it?
Is it early enough to sell construction-site security?
What outreach should be previewed first?
```

That means ConstructionSight can be better than either source product for the security-sales workflow if it preserves evidence, detects transitions, scores timing, and separates verified facts from inferred opportunity value.

## Current branch artifact

This alignment is encoded in:

- `external_gap_models.py`
- `external_gap_registry.py`
- `external_gap_cli.py`
- `constructionsight-shovels-regrid-gaps`

The CLI exposes:

```bash
constructionsight-shovels-regrid-gaps gaps
constructionsight-shovels-regrid-gaps roadmap
constructionsight-shovels-regrid-gaps report
```

All commands support JSON output for later UI/API integration.
