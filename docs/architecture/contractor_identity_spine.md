# Contractor Identity Spine

The contractor identity spine is the first contractor layer in ConstructionSight's Shovels-style overlay.

## Core rule

Contractor identity must be conservative. A contractor name from a permit is useful, but a license signal is stronger. A contractor group signal is helpful, but it must not be treated as perfect unless later evidence supports it.

## First identity signals

The first implementation supports:

- display name
- normalized contractor name
- license number
- license state
- license status
- license classification
- source kind
- contractor group key
- county/state hints
- confidence score
- confidence band
- reasons
- limitations

## Scoring

```text
contractor name present: +35
license signal present: +45
active license status: +10
contractor group signal present: +10
```

A contractor identity without a license remains usable, but it carries a limitation.

## Resolution behavior

Candidate identities are sorted by confidence score and contractor key. A single top candidate resolves. Tied top candidates produce an ambiguous result.

## Relationship to later CSLB enrichment

This phase does not query CSLB yet. It creates the model and normalization layer that CSLB, permit records, Shovels-style data, or user-provided files can feed later.

## Next phase

Later phases can add:

- CSLB source adapter
- contractor license verification
- contractor permit history metrics
- contractor-to-permit graph linkage
- contractor opportunity scoring
