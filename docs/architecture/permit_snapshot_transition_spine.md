# Permit Snapshot and Transition Spine

Permit snapshots are the first Shovels-style event layer in ConstructionSight.

A single current permit record is not enough. ConstructionSight needs to know what changed between observations so it can decide whether a permit became a sales opportunity.

## Core rule

Store source-neutral permit snapshots and derive transitions by diffing snapshots.

Do not rely on a vendor exposing full lifecycle history. If a source provides only the latest permit state, ConstructionSight can still detect movement by comparing repeated observations.

## First snapshot fields

The first `PermitSnapshot` supports:

- source key
- source record ID
- permit number
- jurisdiction
- county
- APN
- site key
- permit type
- work description
- status
- file date
- issue date
- final date
- expiration date
- first-seen date
- job value
- contractor key
- contractor group key
- source updated timestamp
- observed timestamp
- limitations

## First transition kinds

The first transition detector emits:

- new record
- status changed
- value changed
- contractor changed
- date changed
- site changed
- description changed

## Why this matters

This creates the signal layer required for Shovels-style permit intelligence:

```text
permit snapshot at T1
  -> permit snapshot at T2
  -> transition event
  -> opportunity candidate enrichment
```

Later PRs can map Shovels API records, Accela records, EnerGov records, CSV rows, or public permit portal data into this same snapshot contract.
