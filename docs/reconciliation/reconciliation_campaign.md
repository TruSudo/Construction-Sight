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
- private test-drive source registry seeding
- focused module, endpoint, UI, and test-drive regression coverage

Historical source lineage used:
- `agent/command-center-capture-queue`
- `agent/command-center-source-registry`
- `agent/command-center-source-verification`
- `agent/source-attribution-coverage`
- `agent/test-drive-source-inventory`
- `integration/reconcile-source-inventory-2026-09-24`

Validation: CI run associated with the current PR head is pending.

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
