# Parcel-Backed Site Resolution

Parcel-backed site resolution enriches the existing hint-only site resolver with canonical parcel core records.

## Core rule

A site should prefer a parcel-backed match when APN, address, or coordinate hints connect to a known parcel core record. If no parcel core record matches, ConstructionSight falls back to the existing source-neutral resolver and preserves the limitation.

## First matching signals

The first implementation supports:

- exact normalized APN match
- exact normalized address match
- coordinate hint inside parcel envelope
- ambiguity preservation when multiple parcel records match equally
- fallback to hint-only resolution when no parcel record matches
- propagation of parcel geometry limitations into site-resolution candidates

## Scoring

```text
APN match: +70
address match: +20
coordinate inside parcel envelope: +10
```

A single high-confidence parcel match resolves the site. Equal top-scoring parcel matches produce an ambiguous result.

## Geometry limitation rule

Coordinate containment currently uses the parcel envelope, not polygon topology. When a coordinate hint contributes to a polygon or multipolygon parcel match, the candidate must preserve a limitation stating that containment is envelope-only. Geometry limitations from the parcel core record must also carry forward into the site-resolution candidate.

This prevents parcel-backed resolution from being mistaken for survey-grade GIS proof.

## Why this matters

The parcel source registry, schema preview, row preview, and parcel core record layers are useful only if the site resolver can consume them. This phase connects those layers:

```text
public record hints
  -> site-resolution input
  -> parcel core record match
  -> parcel-backed site candidate
  -> opportunity/project graph anchor
```

## Next phase

Future work may replace envelope containment with topology-grade point-in-polygon checks and projection-aware geometry calculations. Until then, parcel-backed coordinate matches remain useful candidate signals, not legal boundary determinations.
