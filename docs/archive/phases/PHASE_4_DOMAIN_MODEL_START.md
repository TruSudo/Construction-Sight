# Phase 4 — Domain Model Start

## Objective

Begin the normalized ConstructionSight data model for downstream adapters and intelligence analysis.

## Completed

Phase 4 has started with two safe foundational modules:

```text
src/constructionsight/domain_types.py
src/constructionsight/provenance.py
```

These establish:

- project lifecycle phases
- entity roles
- relationship type vocabulary
- confidence bands
- numeric confidence-to-band conversion
- provenance/evidence model

## Connector Constraint Encountered

Attempts to commit a larger combined public-record schema module were blocked by the GitHub connector safety filter. Rather than forcing the schema through in one large file, Phase 4 will proceed with smaller modules and tighter review.

## Required Next Modules

The next Phase 4 modules should be added separately:

1. parcel/site model
2. party/entity model
3. permit model
4. planning case model
5. CEQA record model
6. agenda item model
7. document model
8. relationship graph model
9. persistence tables for each domain object
10. tests for all domain validation rules

## Current Phase 4 Status

Started, not complete.

Do not proceed to ingestion adapters until the domain model is added, tested, and locally validated.
