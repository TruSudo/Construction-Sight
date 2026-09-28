# ConstructionSight Full Reconciliation Campaign

## Objective

Integrate every still-relevant capability developed across ConstructionSight's historical branches into one current, hardened application without discarding historical work or reintroducing superseded implementations.

## Canonical line

- Base main: `d3d586b4e66ffd5e49f6466d1c4ad40f94ca0029`
- Integration branch: `integration/full-reconciliation-2026-09-28`
- Integration PR: #201
- Complete branch-tip inventory: `docs/reconciliation/branch_reconciliation_manifest.md`

## Operating rule

Historical branches are evidence and source material. Current hardened main is the architecture target. Missing behavior is ported forward; stale implementations are not blindly merged.

A lineage is complete only when its intended capability is:
1. present on the reconciliation branch;
2. wired into the current application where applicable;
3. covered by retained or updated tests;
4. validated by CI/integration testing; and
5. mapped back to its historical branch tips.

## Reconciliation order

1. Sources & Collection / exact-SCH capture queue / source registry / retained verification / attribution / private test drive.
2. Parcel and ArcGIS acquisition/rehearsal/evidence lineages.
3. Command Center and operator surfaces not already present through the integrated baseline.
4. Lead workflow, duplicate suppression, opportunity enrichment/scoring/action packages.
5. Result ledger, authority, correction/supersession, royalty-facing read surfaces.
6. Contractor/entity identity, universal intake, permit/site/parcel resolution and longitudinal evidence.
7. CEQAnet archive/bundle/report/export/recurring-run and remaining acquisition tooling.
8. Governance, certification, audit, evidence-only and historical branches.
9. Final end-to-end runtime validation and branch cleanup.

## Current progress

### Sources & Collection — in progress

Ported onto the current hardened architecture:
- `src/constructionsight/operator_capture_queue.py`
- `src/constructionsight/operator_source_registry.py`
- source-registry schema compatibility checks in `storage/operator_read_store.py`
- `/api/source-registry` and `/api/capture-queue` operator endpoints
- `--capture-queue` operator configuration
- Command Center source-registry/verification/attribution rendering
- Command Center exact-SCH retained review queue rendering
- explicit source-attribution alias artifact validation and exact SHA-256 identity
- alias-aware retained provenance attribution without granting verification authority
- `--source-attribution-aliases` operator wiring
- private test-drive source registry seeding
- focused module, endpoint, UI, and test-drive regression coverage

Historical source lineage used:
- `agent/command-center-capture-queue`
- `agent/command-center-source-registry`
- `agent/command-center-source-verification`
- `agent/source-attribution-coverage`
- `agent/test-drive-source-inventory`
- `agent/explicit-source-attribution-aliases`
- `integration/reconcile-source-inventory-2026-09-24`

Validation: the first integrated run exposed five compatibility regressions and two import-order findings. Those were repaired without weakening the current evidence-versus-registry authority boundary. The replacement CI run is in progress; vulnerability audits are already passing.

### Already confirmed contained in current main

Representative major lineages already ancestral to main and therefore not candidates for re-merge:
- release/integrated-baseline-2026-09-24
- integration/freeze-6e568d2-2026-09-25
- contractor identity spine
- decision-record spine
- external-intelligence capability spine
- lead duplicate suppression
- lead workflow status spine
- opportunity action package
- opportunity enrichment spine
- parcel site-resolution spine
- permit snapshot-transition spine
- result authority operator
- result-ledger supersession/correction line
- Shovels/Regrid gap alignment
- topology-grade parcel containment
- WKT area-weighted geometry

These branches remain in the inventory until final cleanup so their exact historical tips remain recoverable.


### Parcel / ArcGIS lineage — assessment started

Initial divergent historical tips examined:
- `agent/add-arcgis-proof-bundle-persistence`
- `agent/add-arcgis-rehearsal-http-adapter`
- `agent/add-arcgis-rehearsal-proof-bundle`
- `agent/add-parcel-arcgis-acquisition-gates`

Current-tree findings:
- acquisition bundle models are byte-identical where expected;
- the historical `load_arcgis_bounded_proof_bundle` capability was not lost; it moved to `parcel_source_acquisition_bundle_io.py`;
- current acquisition HTTP retains the historical API surface and adds stricter exact-request/response handling;
- current rehearsal HTTP replaces the historical media-type helper with stricter exact-body validation;
- proof bundle and rehearsal APIs remain present with current hardened implementations.

Disposition so far: these tips are absorbed/superseded candidates, not direct merge candidates. Continue semantic comparison before final classification.
