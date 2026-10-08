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

Validation: the first integrated run exposed five compatibility regressions and two import-order findings. Those were repaired without weakening the current evidence-versus-registry authority boundary. On repaired head `11019fffca784ee6f63a00e71d32966da2bfb512`, Python 3.11 and 3.12 each passed 2,221 tests, 164/164 focused mutation targets, Ruff, strict mypy, compilation, adapter audits, source-adapter coverage, assurance preflight, semantic certification audit, diff hygiene, exact environment identity, and isolated vulnerability audits. The only aggregate CI failure was `ASSURANCE-001` because `governance/reviews/assurance_review.json` is intentionally absent during this active reconciliation campaign.

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


### Parcel / ArcGIS lineage — assessed

Historical acquisition/rehearsal branches were compared semantically against the hardened reconciliation line rather than merged mechanically.

Disposition:
- `agent/add-arcgis-proof-bundle-persistence`, `agent/add-arcgis-rehearsal-http-adapter`, `agent/add-arcgis-rehearsal-proof-bundle`, `agent/add-parcel-arcgis-acquisition-gates`, `agent/harden-arcgis-bulk-rehearsal-proof`, `agent/implement-arcgis-complete-rehearsal-executor`, `agent/record-county-arcgis-bounded-proofs`, and `agent/verify-county-parcel-sources` are superseded by current hardened implementations;
- `feature/parcel-import-preview`, `feature/parcel-record-geometry-normalization`, `feature/parcel-source-registry`, `feature/parcel-source-schema-preview`, and `feature/site-resolution-parcel-enrichment` are already ancestors of the reconciliation line and are classified contained;
- `feature/parcel-fact-assurance` is represented by the current parcel-assurance modules with the same public capability surface plus canonical content-bound report identity validation;
- `codex/parcel-longitudinal-evidence` is represented by the current longitudinal observation/selection implementation with the same service/model surface and stricter immutable collection semantics.

Retention findings:
- acquisition bundle loading and proof-bundle persistence remain present;
- current bounded HTTP execution preserves the historical ArcGIS request/rehearsal capabilities while enforcing stricter exact-request, media-type, response-body, and authorization boundaries;
- parcel fact assurance remains field-specific, provenance-preserving, conflict-retaining, and non-mutating;
- longitudinal parcel observations remain immutable, digest-bound, replay-safe, ambiguity-blocking, and feed only governed current records into parcel assurance;
- parcel import/schema/source-registry and parcel-backed site-resolution functionality are already in canonical ancestry.

No missing Parcel/ArcGIS runtime capability was identified in this pass.

### Command Center and operator surfaces — historical reconciliation assessed

The historical Command Center/operator branches were checked against the current reconciliation ancestry and the locked desktop UI contract.

Contained by ancestry:
- `agent/command-center-evidence-navigation`
- `agent/command-center-filter-watchlist-navigation`
- `agent/operational-integration-gui`
- `agent/ui-lock-command-center`
- `agent/lead-operator-cli`
- `agent/upstream-operator-cli`

The approved desktop design contract remains present in `docs/architecture/official_desktop_ui_lock_v1.md`; historical reconciliation does not authorize a redesign and does not convert placeholder/read-only surfaces into claims of operational capability.

`agent/top-head-quality-and-ops` diverges historically, but its exact capture-queue implementation is byte-identical to the current tree and the remaining operator/bridge surfaces are retained by larger current implementations with expanded ingestion/operator functions and regression coverage. It is therefore classified superseded rather than merged.

Important product-status distinction: the historical UI/operator work is retained, but full product acceptance still requires the backend-authorized commercial paths, persistent watchlist/change notification behavior, complete map/entity/evidence functionality, and final end-to-end runtime validation described by the locked UI contract.


### Lead workflow and opportunity scoring — historical reconciliation assessed

The canonical reconciliation line already contains the principal lead/opportunity spines by ancestry:
- lead duplicate suppression;
- persisted lead workflow status;
- opportunity enrichment;
- opportunity action packages; and
- the operator CLI used to inspect lead state.

Divergent historical branches were checked separately:
- `cleanup/versioned-scoring-profile` is superseded by the current scoring implementation; the same scoring-profile and enrichment capability surface remains present in a later hardened form;
- `remediation/operational-confidence-gating` is superseded by the current tree: its enrichment models and scoring profile are byte-identical, while the current enrichment service is a later retained implementation;
- `feature/opportunity-transition-intake` carries no unique tree delta beyond the already-retained external-intelligence lineage and is classified superseded;
- the older `cleanup/lead-status-rules` lineage remains superseded by the persisted workflow implementation already in canonical history.

The deterministic readiness semantics remain governed: confidence/readiness logic may qualify outreach timing, but it does not authorize bidding, fabricate contacts, or bypass the evidence/review gates defined by the locked UI and operational contracts.


### Result ledger, authority, correction, and supersession — historical reconciliation assessed

The core result ledger and its later money/content hardening are already contained in canonical ancestry. The current tree also contains the later result-authority operator, correction action, and v2 supersession lineages.

Divergent predecessor branches were not merged:
- `agent/result-ledger-authority` is superseded by the later `result_authority_*` model/service/store/operator design. The predecessor used `result_ledger_authority_*` tables/services; the retained successor provides the governed authority head/event history model and operator surface.
- `agent/result-ledger-supersession` is superseded by the contained v2 supersession/correction line. Its ledger service symbols are retained in the current service, which additionally carries fixed-unit money/share calculations and later integrity hardening.
- `feature/result-ledger` and `remediation/result-ledger-content-and-money` are already ancestors of the reconciliation branch and are classified contained.

This closes historical result-ledger reconciliation, not the Royalty Ledger product surface. The locked desktop contract still treats commercial UI destinations as incomplete until the royalty-facing read/action path is wired to governed backend authority and validated end to end.



### Contractor/entity identity, universal intake, permit/site/parcel resolution, and longitudinal evidence — assessed

The Phase 6 historical lineages were compared against the current reconciliation tree with ancestry, file-identity, and semantic checks.

Contained by canonical ancestry:
- `cleanup/persist-movement-identity`;
- `feature/contractor-identity-spine`;
- `feature/permit-snapshot-transition-spine`;
- `feature/parcel-site-resolution-spine`;
- `feature/site-resolution-parcel-enrichment`;
- `cleanup/storage-coverage-matrix`; and
- `feature/artifact-resolution-examples-clean`.

Superseded by later retained implementations:
- `feature/universal-intake-spine`: the current tree retains the historical intake model byte-for-byte and keeps the same inspection/CLI capability while hardening file reads and writes through bounded runtime-artifact helpers. The current opportunity service consumes `UniversalIntakeRecord` directly and regression tests exercise intake-to-candidate transition scoring and limitation propagation.
- `cleanup/storage-summary-cli`: the current storage summary contains every historical table entry plus later parcel source, ArcGIS, longitudinal-selection, and assurance tables.
- `cleanup/persist-parcel-site-records`: later storage retains parcel/site persistence while adding immutable observations, current-selection reports, assurance reports, content-bound identity checks, and replay/integrity protection.
- `codex/parcel-longitudinal-evidence`: already classified superseded by the current immutable longitudinal observation/selection implementation.
- `feature/artifact-resolution-examples`: superseded by the contained clean lineage and later hardened example payloads/tests.

Runtime retention findings:
- lawful source-neutral intake remains format-bounded, provenance-preserving, limitation-preserving, and non-mutating at the inspection boundary;
- universal intake feeds the current deterministic opportunity-candidate layer without treating incomplete or human-review inputs as authoritative;
- contractor identity, permit transitions, parcel/site resolution, longitudinal parcel evidence, assurance, and their persistence/operator read surfaces remain present;
- site/parcel identities and immutable derived records retain collision/replay guards rather than permitting silent identity rewrites.

No missing historical Phase 6 capability was identified in this pass.

Product-status distinction: this closes historical lineage reconciliation for Phase 6. It does not by itself declare a production recurring ingestion pipeline or a fully persisted source-to-domain-to-commercial workflow complete. Final acceptance still requires end-to-end runtime validation of acquisition -> universal intake/source adapter -> canonical site/entity/permit/parcel state -> opportunity/readiness -> governed operator/commercial actions.


### CEQAnet policy, operator, persistence, and CSV evidence lineages — assessed

The historical CEQAnet branches examined here are either ancestors of the current tree or represented by current hardened implementations.

Key retention findings:
- maturity proposal and CSV access-policy services remain present; several service blobs are identical;
- operator export, report, and package implementations remain byte-identical to their historical forms;
- archive and bundle implementations retain the historical public API while adding bounded/staged artifact verification;
- detail execution moved request execution into the governed shared `ceqanet_detail_http` / bounded transport boundary rather than retaining duplicate CLI transport logic;
- persistence execution now validates/prepares the whole plan before mutation and adds atomicity, tamper, and count-drift protection;
- historical CSV evidence-series artifacts and audit evidence remain byte-identical;
- bespoke CSV HTTP adapters were superseded by the shared policy-bound `execute_bounded_http` transport;
- the older CSV export contract was decomposed into current request/inspection models, CSV service, and live execution/verification models without losing the operator capability.

Disposition: classified as `contained` where exact ancestry exists and `superseded` where current implementations retain the capability with stronger architecture.


### Remaining CEQAnet operational lineages — assessed

The unresolved CEQAnet operational branches were compared against the current tree.

Contained by ancestry:
- `agent/ceqanet-ingestion-dashboard-v2`;
- `agent/ceqanet-listing-to-exact-capture-queue`;
- `agent/ceqanet-official-csv-contract`;
- `agent/ceqanet-queue-to-capture-provenance`;
- `agent/ceqanet-source-verification`;
- `agent/governed-ceqanet-capture-preview`; and
- `agent/repair-ceqanet-evidence-partial`.

Superseded by later retained implementations:
- `agent/ceqanet-ingestion-dashboard`: the current inbox/operator implementation is larger and incorporates the later dashboard/capture-queue path with stricter read-only semantics and additional source-registry/capture-queue integration;
- `agent/ceqanet-recurring-run-governance`: its unique tip only removed temporary PR92 publishing tooling, which is likewise absent from the current tree; the current recurring-run service is a later hardened implementation while the verifier blob is retained exactly;
- `agent/fix-ceqanet-windows1252-ruff`: the Windows-1252 replay service and regression test are retained byte-for-byte, while the current CSV parser adds bounded retained-row handling and streaming iteration;
- `feature/ceqanet-detail-enrichment`: the detail-enrichment implementation and regression test are byte-identical in the current tree despite divergent branch ancestry.

Audit-only historical lineage:
- `agent/ceqanet-evidence-repair-partial-v2` preserves a point-in-time branch that promoted CEQAnet to `verified` for guarded manual reads. That authority is stale relative to the later canonical evidence: subsequent bounded HTML automation received HTTP 403 and the current source registry deliberately remains `partial`. The historical verification artifacts are therefore retained as branch history/audit evidence and are not reintroduced into the canonical tree.

The canonical CEQAnet authority boundary remains unchanged: no bypass of the retained HTTP 403, no autonomous scheduler authority, no domain persistence authority from the CSV evidence policy alone, and no source promotion beyond the currently supported `partial` maturity state.



### Governance and historical assurance lineages — assessed

The remaining governance, remediation, audit, and archive branches have been classified.

Most runtime and governance work is already contained in canonical ancestry or superseded by later hardened implementations. Historical defect-closure documents, frozen resolution maps, the pre-remediation audit baseline, and older certification evidence are retained as audit-only history rather than copied onto the current reconciliation head.

This distinction is intentional: prior assurance artifacts describe the exact historical trees they reviewed. The fully reconciled tree requires a fresh final assurance pass and new evidence bound to its own exact commit.

The explicit silent-risk archive tips remain classified as archive recovery points.


### Cleanup and source-readiness lineages — assessed

Core historical behavior was retained:
- lead workflow rules are byte-identical;
- result-ledger and workflow persistence are strict supersets with revision, fixed-unit, CAS, and replay protections;
- parcel/site persistence is a strict superset with longitudinal observations, ArcGIS evidence, current-selection and assurance rows;
- early geometry hardening was superseded by the contained topology/WKT hardening line;
- source verification checklist, promotion, readiness, and registry apply workflows remain present under later authorized/shared-transport boundaries.

Disposition: 49 additional historical branches were classified in the manifest as contained or superseded after semantic/file-level comparison.


### Historical branch inventory — fully classified

The complete 165-tip historical inventory now has no pending lineages.

Final classification at this checkpoint:
- 85 `contained`
- 66 `superseded`
- 7 `reconciled`
- 5 `audit-only`
- 2 `archive`
- 0 `pending`

The remaining CEQAnet operational lineages were closed as follows:
- ingestion dashboard v2, listing-to-exact-capture queue, official CSV contract, queue-to-capture provenance, source verification, governed capture preview, evidence repair, and source-registry controlled apply are contained in current ancestry;
- the older ingestion dashboard, recurring-run governance predecessor, Windows-1252 repair/finalization branch, and detail-enrichment predecessor are superseded by later retained implementations;
- partial evidence-repair lineage is retained as audit-only historical evidence rather than runtime code.

The branch-reconciliation problem is therefore closed at the inventory level. Subsequent work is product integration and runtime validation, not discovery of unclassified historical branches.

### Transition to final integration validation

With the historical branch forest fully classified, the remaining work is to prove the canonical application as one system:
1. exercise source acquisition and retained evidence through universal intake;
2. resolve project/site/parcel/entity/permit identity and longitudinal state;
3. produce opportunity/readiness state and operator-visible evidence;
4. exercise lead workflow and governed commercial transitions;
5. validate result authority, correction/supersession, and royalty-facing reads;
6. validate persistent watch/change behavior and remaining locked-UI destinations;
7. run final whole-tree quality gates and Native Maximum Assurance only after the runtime integration tree is frozen.
