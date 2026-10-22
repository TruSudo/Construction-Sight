# ConstructionSight — system unification

**Controlling assignment:** [owner's verbatim directive](docs/CONSTRUCTIONSIGHT_UNIFICATION_DIRECTIVE.txt).
Follow Phases 1–8 in order. Preserve mandatory historical functionality and safeguards.
One shared investigation engine, the approved native Command Center and a live
Relationship Graph remain the goal. Full unification and functional parity are not complete.

## Phase 8 integration progress meter — owner-visible in integration chats, not the dashboard

**Permanent measurement:** derive this indicator from the existing P8 acceptance
register below, without a second status store, subjective weights, estimated hours,
commit counts or a new development phase. The *integration gate set* is the 15
requirements P8-01 through P8-06 and P8-08 through P8-16. P8-07 (owner data) and
P8-17 through P8-20 (pixel parity, final regression, deployment and permissioned
live-source acceptance) are tracked separately and must still pass before calling
the product complete.

**Checkpoint count at this register:** 10 of 15 integration gates have state **V**
(verified); 5 remain open: P8-01, P8-04, P8-08, P8-09 and P8-11.
Display **67% verified integration gates (10/15)** using a 20-cell filled/unfilled
progress bar. Calculation: round(100 * verified integration gates / 15) to the
nearest whole percent. This number describes *equal-count acceptance checkpoints*,
not the percentage of engineering work finished, time elapsed, or functionality
implemented. Gate sizes differ; no continuous download-like percentage or finish
date can be inferred. A partially connected gate remains open rather than receiving
invented fractional credit.

**Carry-forward instruction for Phase 8 conversations:** Whenever an answer concerns
integration work, show the latest **"Integration acceptance: [bar] NN% (V/15 gates)"**
near the beginning, with open-gate count. First read the current branch's P8 register
and latest CI/visual status; derive V directly from the 15 specified register rows.
Never display this marker in the ConstructionSight product interface. Do not
increment for an unverified commit, passing syntax check, partial feature, or
time spent. Promote a gate to V only when its exact acceptance condition is proven
by focused integration evidence and applicable final-head gates; record evidence
beside that row, so future chats automatically inherit the same factual number.
If a previously verified gate regresses, lower the count until repaired. Do not
mistake this progress bar for full completion: all 20 P8 requirements must also
be accepted, including the five excluded owner/visual/final conditions. Because
the bar is displayed in chat, it refreshes on each response, not continuously
while a chat is idle.

## P8-03/P8-11 original offline source verification reports — native path verified

The exact original source registry, original `build_source_status_report` and
`build_source_verification_evidence_package(check_http=False)` are exposed by
the existing **Sources & Collection** interface as a read-only, downloadable
audit, without creating a second source store, starting remote probes or
promoting source status. Original source access remains selected by the owner
through the existing `--operator-database` boundary. The audit refuses query
flags that would imply remote checks, requires a complete bounded original
registry, and returns an explicit unavailable state if no original database
is selected.

**Evidence:** native route `/api/source-offline-audit`, browser action
`#retained-original-source-audit`, semantic parity and source immutability in
`tests/test_native_original_offline_source_audit.py`, and actual original
source browser workflow in `tests/ui/source_inspection.js`. Application
head `1f42f7a0a4f0629a0f23bd4e16ab3dad20c8d894`: full
Python 3.11/3.12 CI run `39194526497` **success** with **2,825 passed** on
each version, and Command Center browser/visual run `39194526576`
**success**.

**This early offline-only audit did not itself close P8-03.** A later
independently verified native operator/evidence integration, recorded below,
has now accepted P8-03. P8-11 original output/report family accounting remains
separately open; neither gate was awarded by the early audit alone.

## P8-03 original-source controls — verified at application head a4a0cd5

**Original P8-03 sub-checklist: 20/20 verified (100%)** — a functional
source-control equivalence count, not ConstructionSight overall completion.
Original registry, checklist, evidence, status/promotion approvals and bounded
HTTP review are connected to the native interface. Original CEQAnet discovery,
listing, detail, project/document CSV, verified replay/maturity/access policy,
series, immutable successor and explicitly authorized foreground exact-window
recurring run are exposed with inherited original safeguards. Original SMARTS
facility/inspection/compliance and catalog review, approved 1–25 exact county
facility roster, original private SQLite evidence journal and resumable
checkpoint are integrated, while the separate existing daily capture timer
remains unchanged and disabled unless separately explicitly installed.
A positive, review-bound original manual verification checklist is retained
in a private, create-only evidence snapshot, without independent verification
claims or source promotion. Full control-family accounting: draft PR #234.

**Exact application-and-test head `a4a0cd5`:** dual-Python CI
https://github.com/TruSudo/Construction-Sight/actions/runs/39532050943
**success** (2,905 passed, two upstream warnings on both Python 3.11 and 3.12;
Ruff, strict Mypy across 381 source files, JS syntax, dependency integrity
and no known vulnerabilities in either non-exempt dependency scan).
Native browser/USGS
https://github.com/TruSudo/Construction-Sight/actions/runs/39532050957
**success** with all 33 existing functional actions/contracts. Security
remediation pins published `certifi==2026.10.19`, `Pillow==13.0.0` in
runtime/dev and CI `pip==26.2.2` after new October 20 advisories.

**Unchanged boundaries:** Source requests during testing used simulated
transports only; actual permissioned live source checks are P8-20, owner data
P8-07, final pixel parity P8-17, owner-device/timer activation P8-19,
parcel/GIS P8-04, commercial lineage/financial P8-08/09, overall historic
inventory P8-01 and retained report/archive families P8-11. No automatic
source activation, outreach, bid, main merge or approved dashboard redesign.

## P8-10 shared original/canonical watch notifications — verified 2026-10-18

The existing original CEQA/permit source watch, persisted canonical-investigation
watch, and original source-change trigger now have a complete jointly exercised
native inbox acceptance path. The source notification appears when original
retained evidence changes; the canonical notification appears only after its
exact human-reviewed revision passes through the existing worker and commits
new canonical evidence. Both notices retain distinct, deterministic identities,
share the existing read-receipt inbox, avoid duplicate notices per subscription,
and survive browser/server and independent worker restart. Canonical acknowledgment
does not silently archive the original watch; source archive does not mutate
the underlying original source or independent canonical watch. The original
source alert opens the exact source-reconciliation preview and current native
dossier, while the canonical alert opens the current revised shared dossier.

**Evidence:** `tests/test_native_original_canonical_watch_convergence.py`
(both CEQA and permit), `tests/test_native_source_watch_notifications.py`,
`tests/test_native_investigation_watch_notifications.py`, and the genuine
`tests/ui/source_inspection.js` browser journey (automatic in-browser notice
indicator, original-to-canonical navigation, committed revision, joint inbox
and durable read receipts). Published application/test HEAD `a3886baccaa3185bfca51ff09ccd1e383c079394`:
CI workflow `39185234856` **success** with **2,818 passed** on both Python
3.11 and 3.12; Command Center visual/browser workflow `39185234857`
**success** (not an exact pixel-match certification). These tests close P8-10,
not separate original-data or live-source access P8-07/19/20. No external
notification delivery, collection authority or commercial promotion is inferred.
The original independent watch stores and approved dashboard visual structure
are preserved.

## P8-09 result-history continuation — 2026-10-18

The existing native Lead Console now inspects immutable original result/correction
history for its exact retained canonical workflow. It reuses
`read_validated_result_history` and `_outcome_revision`, including validation of
superseded share receipts, revision digests, package/candidate lineage and exact
money units. Fingerprint, review, workflow and result records share one read
snapshot. Unrelated original workflows are not joined by title, site or status.

Expandable history in the existing workflow table identifies the current revision,
preserves each superseded correction/reason/digest and exports the same validated
workflow/source snapshot. Minor-unit amounts use decimal integer strings so browser
JSON cannot round large retained amounts. A newer source revision leaves the original
history attached to its handoff evidence and keeps source review visibly required.
No history implies no inferred outcome. Historical wins or calculated shares do not
verify awards, contracts, royalty entitlements, payments or commercial authority.

Local acceptance: 12 new HTTP/history regressions passed, with final targeted reruns
for odd cents beyond JavaScript's safe-integer boundary and the accepted 100/rejected
101 revision limit; 24 existing native handoff, original lineage and result-integrity
regressions passed. The expanded real-browser native investigation journey passed
inspection/export, unchanged database bytes, source revision/reload and preserved
dossier/review controls. Ruff, strict Mypy (357 modules), JavaScript syntax, dependency
integrity and existing map/dossier runtime checks passed. Published exact-head Python
3.11/3.12 and complete browser/visual gates are tracked by draft PR #234; local
acceptance alone does not claim their completion.

This is read-only result-history continuity, not closure of all P8-09 operations or
Phase 8. Native result-apply/correction operations and broader historical workflow
equivalence still require their own governed integration/acceptance. The approved
dashboard layout/reference, source activation and commercial action controls are
unchanged. Main merge still requires explicit owner authorization.

## Phase 8 finish line — owner-requested scope reconciliation (2026-10-18 UTC)

**Scope:** Finish the mandatory functionality already specified in the controlling
directive and preserved original/newer implementations inside the approved native
Command Center. Account for historical work; connect or prove equivalent behavior.
No new product features, redesign, unrelated refactor, universal jurisdiction
coverage, future imagery service, hosted multiuser product or new governance
program. A historical item marked planned is not an implemented capability to
restore. AI must remain optional. Separate stores are permitted; competing
investigative realities and permanent dependence on a second dashboard are not.

**Assessment baseline:** application/test HEAD `2bc29ba` (reviewed original-source
revisions); prior accepted source `825a717`. This is a documentation/source
reconciliation, not a new runtime certification. Existing exact-source CI results
below are retained. The subsequent continuation independently retrieved the latest
revision's completed CI/browser results and verified its published tree against
local `2bc29ba`; P8-06 is now accepted. Later changes need their own final gates.

**Evidence checked:** original directive sections II, IV–XI, XII Phase 8, XIII and
XVI; Phase 1 preservation JSON; current original/native HTTP handlers; native source,
replay, lineage, preview and export bridges; original guarded operator services;
watch-change and product-integration services; native commercial handlers; existing
parity tests and the calibrated visual comparator. The preservation baseline contains
193 branch records and 83 non-ancestor contribution inventories covering 302 unique
paths, including 141 Python source paths. Those are historical inventory sizes,
not counts of unfinished features. Its own scope explicitly does not establish
functional equivalence. Static import absence likewise is not proof that no
equivalent implementation exists.

**Acceptance register (20 obligations):** V = verified within the cited earlier
acceptance scope; O = open implementation/equivalence obligation; P = implemented
or assembled but final verification outstanding; B = owner-data/device/current
source access needed. V is retained evidence, not a fresh execution on `2bc29ba`.
Counts: **10 V, 6 O, 1 P, 3 B**. These obligations differ greatly in size; do not
convert 10/20 into full-product completion or treat outstanding obligations as
bugs. This fixes the acceptance denominator, not the number of code changes.

| ID | Required behavior | State and existing evidence | Exact closure condition |
| --- | --- | --- | --- |
| P8-01 | Complete historical capability accounting | O — frozen 302-path ledger now tracks 83 divergent historical branches (95 exact retained blobs, 164 present nonmatching/unproven, 43 absent). This is a complete file inventory, NOT functional equivalence; half-up/half-even financial tie divergence and historical CSV parser/transport differences require explicit disposition; see `docs/audits/p8-01-historical-capability-disposition-first-pass.md` and `docs/audits/p8-01-historical-path-ledger-2026-10-21.json` | Give every mandatory historical behavior an implemented native path or a tested equivalent; explicitly classify recovery-only/development assets and superseded implementations. No unidentified mandatory remainder. |
| P8-02 | Original source inspection and attribution | V — `test_native_original_registry_parity.py` compares 16 original/native HTTP read contracts; source/SMARTS tests cover additional views | Retain exact attribution, filters, pagination, evidence limits and original-byte preservation through final regression. |
| P8-03 | Source acquisition, verification and registry controls | V — twenty original-source operational subcheckpoints accepted. Native CEQA source review/discovery/detail/listing/CSV/replay/maturity/policy/series/manual recurrence, SMARTS catalog/roster/manual source-journal collection with separate unchanged daily timer, approved registry authority and durable manual evidence retention. Exact code/test `a4a0cd5`: Python 3.11 + 3.12 each 2,905 passed, no known security vulnerabilities, full browser/USGS success; owner-source permission separate. | Reconcile each existing operational control with its native/worker equivalent and expose missing routine operator controls with the original approval/access safeguards. Setup-only CLI tools may remain documented deployment tools; a CLI alone does not replace a required native operator workflow. |
| P8-04 | Parcel/GIS investigation operations | O — parcel candidates are exposed; original schema/row review, authorized ArcGIS acquisition, proof persistence and parcel/site resolution are not all demonstrated as one native workflow | Demonstrate authorized retained GIS/parcel evidence through review, governed persistence/resolution and the same dossier/map/graph; preserve ambiguity and exact source/proof identities. No invented coordinates or automatic same-project inference. |
| P8-05 | Missing original-source replay | V — scoped replay tests, independent-worker browser journey and genuine retained CEQA acceptance at `825a717` | Preserve bounded page review, atomic approvals, overlap rejection, full-scope rescan and restart without duplicates. Owner-data execution is P8-07. |
| P8-06 | Reviewed changed-source handoff | V — published `3035fb9` has exact tree `dc93cd89d831522067a420d1ce6481c74c80d8ba` of local `2bc29ba`; full CI/browser accepted | Preserve exact-source acceptance: 2,777 tests on each Python version, full quality gates and independent-worker browser revision/delayed-dialog journey; earlier evidence and reassessment remain intact. |
| P8-07 | Intended owner's retained-data reconciliation | B — fixture/genuine offline capture acceptance exists; owner's complete selected data has not been reconciled | Identify actual original/native stores and retained artifacts; process all reviewed pages, resolve/hold conflicts, rescan and account for every selected record without modifying originals or duplicating work. Explicitly bounded scope, never countywide completeness. |
| P8-08 | Investigation-to-qualified-lead handoff | O — investigations remain unassessed; native commercial writes resolve `current()["rows"]`; original `product_integration_service` provides review/dedupe/workflow behavior not proven equivalent for canonical investigations | An explicitly reviewed eligible investigation reaches the existing lead/commercial workflow with stable lineage, dedupe, evidence-backed readiness/reasons and contact/authority gates. Unqualified investigations remain visible and blocked from unauthorized commerce. |
| P8-09 | Historical commercial workflow continuity | O — validated history, finance lineage and no-send previews exist; original transition/result-apply services are not exposed by the native handlers inspected | Continue an eligible retained workflow through authorized transitions and outcome/correction operations from the native UI, or prove an equivalent preserving its exact history, money and source/investigation attribution. Historical shares never automatically become native entitlements/payments. Physical database merging is not required. |
| P8-10 | Source/investigation watches and material alerts | V — existing source and canonical watches both project into one native notification inbox; full cross-source worker, restart, read/archive/acknowledge, browser UI/dossier and duplicate tests passed on `a3886ba` (2,818 Python tests on 3.11 and 3.12; visual browser workflow successful). No background polling or external delivery inferred. | A watched canonical/original source change produces the correct persistent, deduplicated native notification with exact lineage, including worker restart and read/archive behavior. External delivery only if already implemented and separately authorized. |
| P8-11 | Complete retained report/export equivalence | O — native retained-chain-report ZIP reuses original package/archive validators; broader report/control equivalence is still unaccounted | Enumerate original chain/report/evidence/bundle/package/archive/verify outputs and audit exports; prove each required native output is equivalent and usable without the old dashboard. Do not duplicate a proven exporter or treat packaging an existing report as proof of creating that report. |
| P8-12 | One investigation across views | V — Phase 5/8 inventory, map, dossier, evidence, lineage/recovery browser evidence | Preserve common IDs and committed revisions across overview, Lead Console, Project Intelligence, map, network, evidence and dossiers; filters, unmapped queue, restored histories and open-dossier refresh stay consistent. Commercial eligibility is separately P8-08. |
| P8-13 | Embedded/expanded live and historical graph | V — Phase 6 acceptance and later paused/closed graph worker journeys | Preserve shared graph state, actual committed events, review propagation, replay, reconnect, saved views, filters, evidence and map/dossier navigation. Display pause must not stop engine or current-dossier updates. |
| P8-14 | Integrated safeguards | V — Phase 7 acceptance table and repaired historical tests below | Preserve those guarantees on every newly connected path; no weakened source access, provenance, identity, transaction, recovery, financial or commercial approval boundary. New paths need applicable checks, not blanket recertification of unrelated code. |
| P8-15 | Existing native commercial functions | V — native bid/royalty, outreach preparation/tracking, commercial browser and Phase 7 financial acceptance | Preserve explicit manual controls, exact money, request evidence, immutable versions/contracts and corrective entries. Existing source-row functionality does not close P8-08/09. No real sale or paid royalty is required to prove software behavior. |
| P8-16 | Durable background retained-data operation | V — Phase 3/4 worker, inbox, bounded processing, idempotency/restart and later independent-worker acceptance | Preserve automatic authorized intake-to-investigation progression, dependencies, change reassessment and failure visibility without requiring an open browser or ChatGPT session. Device/live operation is P8-19/20. |
| P8-17 | Approved visual parity | O — structure/fonts and regression ratchet pass; calibrated pixel comparison fails | Approved 1672 × 941 reference, fonts and structure pass the existing calibrated regional comparison. Preserve reference/hash, masks, calibration and thresholds; ratchet success alone does not close this item. Any irreducible reference discrepancy requires explicit owner disposition, not silent threshold relaxation. |
| P8-18 | Final integrated regression acceptance | P — full gates exist for `825a717`; later source acceptance remains pending | After remaining code changes, freeze the actual final application/test revision and pass applicable Python 3.11/3.12, Ruff, strict Mypy, JS, dependency, browser, identity/evidence, cross-source, recovery and visual gates. Prove realistic retained-data journeys plus meaningful failure cases. Do not rerun unchanged full suites merely for documentation edits. |
| P8-19 | Owner-device deployment | B — Zorin/systemd installation and real startup acceptance open | Clean/reproducible install on intended laptop, reviewed local paths/configuration, independent worker/timer, restart, backup/restore and visible failure/disable/rollback behavior. No automatic source authorization from installation. |
| P8-20 | Permitted live cooperating-source acceptance | B — live source operation left open from Phases 3–4 | With current source-specific permission and separately reviewed activation, demonstrate actual bounded source acquisition through retained evidence, investigation, reassessment and synchronized UI. Record coverage/identity limits and stop blocked sources; do not infer authority from a historical capture or reachable URL. |

**Evidence locations for the open implementation obligations:**
- P8-01: `docs/audits/unification-preservation-baseline-2026-10-16.json`,
  `governance/capability_contract.toml`, original directive section II.
- P8-03/04: `operator_services/`, `parcel_source_cli.py`, `upstream_operator_service.py`,
  `command_center_sources.py`, `ceqanet_background.py`, `investigation_runtime.py`.
- P8-08: `product_integration_service.py`, `lead_review_service.py`,
  `lead_dedupe_service.py`, native `live_command_center.py` commercial POST handlers.
- P8-09: `operator_services/lead_workflow_transition_service.py`,
  `operator_services/result_authority_apply_service.py`, `command_center_legacy_*.py`,
  `command_center_retained_previews.py`, `command_center_commercial.py`.
- P8-10: `operator_watchlist.py`, `watch_change_monitor.py`,
  `storage/domain_store.py`, `storage/watch_change_store.py`, native notification routes.
- P8-11: `ceqanet_operator_*.py`, `ceqanet_chain_cli.py`, `audit_package_cli.py`,
  `command_center_legacy_export.py`.
- P8-17: `tests/visual/compare_mockup.py`, recorded reference/calibration and existing
  browser acceptance. This pass did not generate a new screenshot or pixel score.

**Execution order:** P8-06 is now accepted; finish P8-01's behavioral
mapping using the bounded existing inventory, assigning each discovered gap to
P8-03/04/08/09/10/11 rather than opening new feature work. Close those integrations
in dependency order (source/parcel -> reviewed lead -> commercial continuity;
watches and exports alongside their dependencies), then P8-17 and final P8-18.
Prepare owner-data/device/live acceptance in parallel where configuration permits;
execute P8-07/19/20 when the required data, device and source authority are available.

**Stop rule:** Implementation is complete when P8-01–06 and P8-08–18 are closed
with evidence on the final tree. Full Phase 8 acceptance also requires P8-07/19/20.
There must be no mandatory operator task requiring the original dashboard.
Keep the original implementation and history preserved; retirement and merge into
main remain separate owner decisions. Optional future capabilities, obtaining
contracts, sending outreach and expanding access are not additional finish criteria.
Any newly found missing behavior must cite the original requirement/historical
implementation and fit this register; genuinely new scope requires an owner decision.

**Honest limitation:** The endpoint/service review establishes concrete gaps and
fixed closure criteria, not exhaustive semantic equivalence across 83 historical
contribution inventories. P8-01 remains explicitly open until that mapping is
complete. Do not claim a complete atomic task count, percentage or finish date
from this register. The scope is fixed; the remaining implementation size is not
yet fully measured.

### Bounded command-family reconciliation

All **63 current executable entry points** in `pyproject.toml` are assigned below.
Names are suffixes after `constructionsight` (`(base)` means the unsuffixed command).
This is complete entry-point accounting, not proof of every historical branch behavior.
Historical non-CLI modules and different branch versions remain subject to P8-01.

| Behavior family | Existing command suffixes | Remaining obligation / disposition |
| --- | --- | --- |
| Launch/compatibility | `(base)`, `-command-center`, `-operator`, `-desktop` | P8-12; original launchers preserved for comparison, native launcher is the sole target experience. |
| Shared investigations/intake | `-investigations`, `-intake`, `-opportunity-intake` | P8-08/12/16 |
| Candidate docket/external intelligence | `-candidate-docket`, `-external-intelligence`, `-shovels-regrid-gaps` | P8-03/08; staging, gap detection and bounded enrichment/review must be accounted for; no new external vendor subscription is implied. |
| Parcel/site operations | `-site-resolution`, `-parcel-sources`, `-upstream`, `-parcel-use` | P8-04 |
| Source authority/registry | `-source-status`, `-source-readiness`, `-source-checklist`, `-source-promotion`, `-source-plan` | P8-03 |
| Commercial workflow/results | `-leads`, `-results` | P8-08/09 |
| Contact operations | `-cslb-contacts`, `-contact-call-list` | P8-08/15; native SMARTS import/call-list exists; CSLB retained-source and canonical-investigation handoff equivalence remains open. |
| SMARTS retained review | `-smarts-preview`, `-smarts-review`, `-smarts-snapshot-diff`, `-smarts-snapshot-history`, `-smarts-inspections`, `-smarts-compliance`, `-smarts-source-review`, `-smarts-catalog` | P8-02/03; status/change/parcel views exist, inspection/compliance/catalog/source-review operations still require explicit equivalence. |
| SMARTS acquisition/scheduling | `-smarts-collect`, `-daily-collection` | P8-03/16/19/20 |
| CEQA acquisition/access evidence | `-ceqanet-listing-plan`, `-ceqanet-listing-execute`, `-ceqanet-recurring-run`, `-ceqanet-csv`, `-ceqanet-detail-execute`, `-ceqanet-maturity`, `-ceqanet-access-policy`, `-ceqanet-evidence-series` | P8-03 |
| CEQA offline transformation/retention | `-ceqanet-fixtures`, `-ceqanet-vocabulary`, `-ceqanet-results`, `-ceqanet-detail`, `-ceqanet-enrichment`, `-ceqanet-chain`, `-ceqanet-persistence-preview`, `-ceqanet-write-plan`, `-ceqanet-persistence-apply`, `-ceqanet-reviewed-import` | P8-03/11 |
| CEQA operator reports/archives | `-ceqanet-operator-package`, `-ceqanet-operator-report`, `-ceqanet-operator-bundle`, `-ceqanet-operator-bundle-verify`, `-ceqanet-operator-export`, `-ceqanet-operator-archive`, `-ceqanet-operator-archive-verify` | P8-11 |
| Engineering/deployment/audit utilities | `-storage-summary`, `-audit-package`, `-certify`, `-supply-chain`, `-build-basemap` | P8-11/14/19; certification, map building and storage inspection may remain engineering/setup tools; required audit outputs still need native equivalence. |

The preserved capability contract has eight implemented/guarded capability families
and two explicitly planned families (outreach sending and hosted multiuser access).
Neither planned family authorizes enabling transport or introducing a hosted product.
Preserve the current manual outreach/bid workflow; no new email delivery integration
is required merely because an older plan mentions one.

For historical non-ancestor contributions, the 141 Python paths group into source
acquisition/access/retention, parcel/GIS, intake/opportunity/workflow/result, existing
native projections, and assurance/storage. Missing/superseded paths remain pinned in
the preservation JSON and the Phase 7 historical-disposition table. Assign their
behavioral differences to the obligations above; file/blob identity alone cannot
close them. No source, commercial, parcel or report family is excluded by calling
its existing operational command an engineering utility.

## Current continuation — retained source-watch notifications (gates pending)

The original validated source-watch projection now feeds native Notifications.
A triggered CEQA/permit watch yields one stable local attention item; native read
receipts survive restart without changing the original source or watch. Rearming
acknowledges the previous trigger, archiving removes current attention, and a later
change after rearming creates a new unread identity. The normal five-second UI
refresh updates the unread indicator with overlap suppression and visible stale
status on request failure. Exact source inspection and shared-engine comparison
open from a notice; the same current dossier is available without approving the
incoming revision. Closed/replaced dialogs reject delayed inspection replies.
A damaged original watch yields a visible source-store warning while preserving
native notifications. No network acquisition, external notification delivery,
commercial qualification, source mutation or source-revision approval is added.

Local acceptance: **28 focused notification/source/watch/state tests** and **51
revision/registry/notification/lineage/commercial/Phase 7 regressions** pass (overlap
between runs is not summed). Ruff over src/tests, strict Mypy over 355 source files,
changed JavaScript syntax and diff hygiene pass. Browser acceptance now includes an
independent original-source change, automatic unread indication, exact source/current
dossier navigation, later reviewed worker revision and read state after reload.
Current-source full CI/browser acceptance remains pending publication.

P8-10 remains open for canonical investigation-only watches and complete shared
watch/notification equivalence. The existing original-source-to-native-inbox path
is implemented; do not call all watch integration complete from this slice.

## Exact recovery checkpoint

- Latest Phase 8 continuation: published `825a7174c402dd7fc2a8aaca539092d41dcda5ea`;
  exact tree of preserved local `11df9be`:
  `0c6fa8d2d9ea9b8b814d501474b7fabe37204fa6`. Source-scoped replay, overlap
  rejection and original attribution-alias parity are implemented. Exact-head
  browser/USGS and both full Python quality gates pass (2,770 tests each). Structure,
  fonts and the unchanged visual ratchet pass; exact pixel parity remains open.
- Development branch: `agent/unification-implementation-2026-10-16`, draft PR #234. Latest fully verified Phase 8 application/test source: `825a7174c402dd7fc2a8aaca539092d41dcda5ea` (full quality gates and browser workflow passed). Phase 7 remains accepted at `3429b14f847163083dfdf32b181bc231d17605c6`.
- Latest source accepted for Phase 6: `5c03cd80cde497b2dfc0e3533a913000db280812` (anchored historical snapshots, retained-history timeline/comparison, saved layouts, source/date/confidence controls, source grouping, activity highlighting, and bidirectional graph/map navigation). Phase 5 remains pinned to `44e80090219a0ad0938dbec44848233d089bcf2d`.
- **Phase 7 implementation and regression acceptance is complete** for the controlling directive and currently integrated runtime. The final reconciliation and exact-source results below supersede the older continuation checkpoints. Phase 8 is now in progress; preserve the original interface and all historical assets.
- Phase 5 native integration is implemented. Exact-source acceptance results are recorded below.
- Main remains `4c8f8eaf08653e2d571b0df821b862dcc9b158ac`; no merge or owner-device/source activation.
- Phase 6 implementation acceptance is complete for the controlling Phase 6 directive: the same persisted investigation graph and committed worker events drive embedded/full-screen views, bounded anchored historical replay, connection recovery, dossiers and bidirectional map navigation. Phase 7 safeguard reconciliation is now accepted below; next follow the unchanged directive into Phase 8, without claiming real-source/device operational acceptance.
- Operational checks still open: owner-Zorin/systemd deployment, permissioned live-source background acquisition, and real live cooperating-source acceptance from Phases 3–4.
- Preserve all original interfaces, historical branches and assurance evidence through Phase 8 acceptance.

## Phase 8 — IN PROGRESS: native preservation and original-workflow parity

**Source revision integration (2026-10-18, full gates accepted at `3035fb9`):** A changed original
CEQA/permit observation can now be explicitly reviewed against its exact current
native evidence and handed to the existing worker as a retained source revision.
The worker rechecks the previous evidence under its knowledge/completion
transaction, retains earlier evidence and runs the existing relationship
reassessment. It rejects stale, older or already-retained historical snapshots.
Page approvals still queue only missing observations and hold differences for
individual review. Existing missing-source approval/job payloads retain their
original shape and identity; no database migration or parallel engine is added.
The existing reconciliation dialog opens the current shared dossier, binds
revision consent to both evidence identities and rejects late queue/audit
responses after the operator opens another view. Seven new tests pass for both
families, prior audit preservation, stale-worker rejection, chronology, existing
association reassessment and HTTP guards. Twenty-seven original runtime,
lineage, commercial and registry regression tests plus eleven existing replay
tests passed locally; Ruff, strict Mypy (355 modules), JS syntax and diff hygiene
pass. Full Python/browser gates, including an independent worker updating an
open dossier while its source revision review response is delayed, now pass.
[CI 39091426185](https://github.com/TruSudo/Construction-Sight/actions/runs/39091426185):
Python 3.11 **2,777 passed**, two warnings, 318.90s; Python 3.12 **2,777 passed**,
two warnings, 309.59s. Quality/dependency gates pass.
[Browser/USGS 39091426183](https://github.com/TruSudo/Construction-Sight/actions/runs/39091426183)
passes, including 33/33 actions/contracts. Structure/fonts/ratchet pass; all eight
calibrated pixel regions still fail. These results close P8-06, not P8-17/18.

**Verified continuation (2026-10-18):** Sources & Collection
now reviews the current filtered CEQA/permit page for shared-investigation replay.
The bounded plan binds source digests and native evidence state; missing snapshots
queue with their individual and batch approval audits in one transaction through
the existing worker. Exact retained observations are skipped; conflicts stay held.
Subsequent pages require review and a final rescan; one page is not a complete
migration claim. Original records, financial authority and the approved layout
remain preserved. Nine new tests cover full filtered-scope traversal, strict
confirmation, stale evidence, concurrent arrival, atomic rollback, restart,
idempotency, HTTP guards and database separation. Exact retries retain the
original approval. An overlapping individual/page approval with a different
reason fails under the existing queue writer reservation before any batch jobs
or audits commit; after processing, a fresh review can queue remaining sources.

The original retained source-attribution alias artifact is now passed through
the native launcher to the same validated registry projection. Its digest and
application status remain visible; it grants no source access or project identity.
Sixteen original/native HTTP read contracts compare identically with mixed
CEQA/permit records. Four new tests also cover retained startup configuration,
invalid authority, no-follow artifact reads and exact CLI forwarding.

- Local checks: eleven replay/HTTP tests, sixteen alias/source tests and sixteen
  original worker/job tests passed; Ruff over all src/tests, strict Mypy (355
  modules), JavaScript syntax and diff hygiene passed. The earlier local full
  suite passed 2,765 tests before the later alias/overlap additions.
- [Exact-head Python CI 39090275881](https://github.com/TruSudo/Construction-Sight/actions/runs/39090275881):
  **2,770 passed on Python 3.11** in 317.73s and **2,770 on Python 3.12** in
  373.93s; two non-failing upstream Typer/Click warnings each. Ruff, strict Mypy
  (355 source files), JavaScript syntax and dependency integrity/vulnerability
  audits passed. No known dependency vulnerabilities were reported.
- [Exact-head browser/USGS 39090275804](https://github.com/TruSudo/Construction-Sight/actions/runs/39090275804)
  passed, including mixed CEQA/permit page review, independent worker processing,
  per-job audits, rescan, idle restart, shared dossier/evidence identities and
  original attribution aliases. Existing graph/map, commercial, backup/restore,
  **33/33 actions and 33/33 complete contracts** remain passing. Structure/fonts
  and the visual ratchet pass; exact pixel parity fails and remains open.
- An additional offline acceptance used the genuine retained July 12 CEQAnet
  CSV execution (source body SHA-256 `5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163`).
  Both original filings reached two distinct unmapped/unverified investigations;
  rescan found zero missing sources, a fresh worker processed zero duplicate
  jobs, and original database/execution bytes remained unchanged. No source was
  fetched and no current construction activity or independent identity is proved.

**Verified application/test source:** `825a7174c402dd7fc2a8aaca539092d41dcda5ea`.
Original operator assets, historical branches, the previous native association-review
acceptance, and the shared investigation graph remain preserved. The legacy database
is an explicitly selected, separate source; displaying its records does **not**
automatically reconcile them into the canonical native site investigation.

**Implemented and tested in the approved native Command Center:**

- Overview and Site Map now use the same retained investigation identities. The
  automatic USGS provider is resolved before generating tile URLs; all provider
  modes, failure fallback, region changes during requests, and stale-region
  exclusion are exercised through the actual renderer. Unavailable or unqueried
  stores no longer assert a completed investigation scan.
- Native inventory, dossiers and overview now compare the existing immutable
  event-tip ID with the sequence, detecting restored sibling histories even
  when their event counts agree. Mixed-lineage map pages are rejected, and an
  open overview dossier follows worker revisions. No database migration or
  evidence/authority changes. Thirty focused investigation/graph/service tests
  and forty original workflow/assurance tests passed locally; Ruff and strict
  Mypy (355 modules) passed. Browser run `39057566189` passed all 33 actions and
  33 complete contracts, retained worker/dossier refresh, and the live USGS probe.
  Native legend spacing improved measured map error; watchlist star fill was
  corrected. Exact approved-reference pixel parity remains open; comparison
  thresholds, masks and the reference asset are unchanged.
- A current dossier opened from the expanded/paused graph or another workspace
  without an inventory now follows the same worker revision through the existing
  five-second UI timer. Display pause does not freeze that current dossier.
  Closed dialogs stop polling; active inventories retain their existing refresh
  ownership. Slow polls do not overlap, changed/closed modals reject late replies,
  and recovery clears only this poll's own stale warning. Actual helper checks
  pass; the expanded graph/paused-worker browser journey now covers this handoff.
  Exact-source full browser acceptance passed at `397adfc`, including an actual
  independent worker revision reaching the current dossier while its graph stays paused.
- Exact-source [Python CI 39057566237](https://github.com/TruSudo/Construction-Sight/actions/runs/39057566237):
  **2,757 passed on Python 3.11 and 2,757 on Python 3.12**, two non-failing upstream
  warnings each; Ruff, strict Mypy, JS syntax and dependency audit passed.
  [Browser/USGS 39057566189](https://github.com/TruSudo/Construction-Sight/actions/runs/39057566189)
  passed. Pixel parity did not pass; the prior lower-error source icon is retained
  and the existing visual ratchet passes. The accepted legend change reduced map
  mean error from 11.055 to 9.982 and local peak from 34.674 to 32.999. All other
  existing acceptance gaps below remain open; this is not Phase 8 completion.
- The existing evidence-bound association preview, explicit associate/reject review,
  stale-evidence rejection and canonical map/graph reassessment remain intact.
- Sources & Collection now reuses the original read-only CEQA/permit registry,
  source-revision digest, bounded source review queue, exact candidate/evidence
  previews, parcel candidates, original entity-key index and neighborhood, dated
  historical milestones and source-scoped geographic footprint, with JSON exports.
  Missing source databases are explicitly unconfigured, not fabricated zero results.
- Configured original immutable CEQAnet exact-SCH capture and listing/review
  ingestion artifacts can be inspected without acquiring, importing or qualifying
  any source claims. Their original validation and no-follow artifact readers remain.
- Configured original SMARTS journals/snapshot history can be integrity-checked and
  paged; selecting a recorded change invokes the original exact current-snapshot
  parcel candidate review. Ambiguous or stale matches remain candidates, and
  private original CSV contents are not exposed.
- Original CEQA/permit source-specific watches can be added and archived through
  an exact-origin, local, existing watchlist-table-only database boundary.
  They remain separate from native commercial lead watches and start no polling,
  notification or commercial effects.
- Original persisted workflow/result records remain inspectable in native Bid Studio
  and Royalty Ledger with their limits explicit. Native Bid Studio additionally
  reuses the original four guarded **manual preview** services: unsent outreach,
  explicit request-evidence validation, human-entered exact-money pricing, and
  an internal proposal draft. Each requires current persisted workflow authority.
  No contact, pricing terms, bid or external send is authorized by those previews.
- Phase 8 exact-source reconciliation now compares an explicitly retained original
  CEQA/permit observation against the deterministic source identity and current
  evidence in the canonical investigation store. An exact same-origin,
  human-confirmed, source-digest-bound request can enqueue a missing source
  snapshot through the **existing durable investigation worker**. The original
  source remains unchanged; the worker must commit the observation before the
  canonical graph/dossier changes. Existing or contradictory native observations
  cannot be silently replaced. No source replay proves project identity or grants
  commercial authority.
- The original CEQAnet chain-report package, evidence report, bundle manifest,
  verification and deterministic ZIP archive are now available through the
  native Sources & Collection panel. An operator must select a retained exact
  chain report and confirm its SHA-256 before generating a verified local ZIP.
  Downloads are served from the private local artifact area only after the
  existing archive verifier passes. Repeat exports must match the exact
  underlying original operator package. No remote collection or external
  commercial action is performed.
- All additions remain confined to existing Command Center workspaces; the
  approved overview/sidebar structure was not replaced or redesigned.

**Latest verified original workflow transition-history integrity:**

- Both original-source → historical workflow and historical-workflow → native-source
  lineage now verify every persisted original workflow status event against the
  immutable event rows, in chronological order, including its exact ID, status
  transition, timestamp, reason, payload and legal transition matrix. Missing,
  altered, reordered or additional events fail closed; the bounded read does not
  modify the original records or grant native sales/payment authority.
- [Python CI](https://github.com/TruSudo/Construction-Sight/actions/runs/39041837361):
  **2,750 passed** on Python 3.11 and **2,750 passed** on Python 3.12,
  two non-failing warnings on each. Ruff, strict Mypy and JS checks passed.
- [Visual and USGS](https://github.com/TruSudo/Construction-Sight/actions/runs/39041837289):
  both jobs passed, including the new two-event history and original financial
  lineage in both native directions, with existing map/graph/browser safeguards.
  Exact approved-mockup pixel parity remains an open separate criterion.

**Latest verified original workflow → exact source reverse attribution:**

- Historical records in native **Bid Studio** and **Royalty Ledger** now offer
  an explicit read-only reverse lookup. The operator selects the exact original
  CEQA or permit family and source record ID. The existing normalized source
  candidate identity must equal the persisted original workflow base-candidate
  ID. The review package, original workflow, complete result revision chain
  and every retained historical share are independently integrity-checked.
  Missing, mismatched or contradictory records are rejected; **name, address,
  APN and fuzzy similarity never create the relationship**.
- The native canonical dossier navigation is enabled only when the exact
  original source is also the currently retained native observation; otherwise
  the attribution remains an original-source candidate without a native link.
  The original database remains read-only and no snapshot is fetched. Original
  workflow status, historical shares, bids and payments stay informational;
  none is promoted to verified entitlement or commercial authority.
- [CI 39038800038](https://github.com/TruSudo/Construction-Sight/actions/runs/39038800038):
  **2,747 passed on Python 3.11 and 2,747 passed on Python 3.12**,
  with two non-failing warnings each; strict Mypy, Ruff and JS syntax passed.
- [Command Center / USGS 39038800032](https://github.com/TruSudo/Construction-Sight/actions/runs/39038800032):
  both jobs passed, including negative and positive reverse-attribution
  browser checks, original financial views, native investigation navigation
  and all configured functional-contract checks. Exact approved-mockup
  pixel parity remains unverified.

**Latest verified canonical dossier → exact original finance lineage:**

- The approved native shared-investigation dossier now displays a bounded
  exact-source selector for CEQA/permit memberships. Historical original
  workflow/outcome evidence is shown there **only** when the preserved original
  record, the deterministic native source entity, its current evidence ID,
  the original source SHA-256 and the canonical investigation all match.
  Disagreement, missing original data or stale evidence fails closed without
  joining historical money or creating project/commercial authority.
- A controlled browser fixture exercises a separately retained native CEQA
  investigation with original workflow and calculated share, plus an unmatched
  original source whose worker replay still requires explicit approval. The
  native dossier can export the exact matched lineage JSON. Original source
  and finance records remain unchanged and cannot establish verified payment,
  royalty entitlement, binding bid or a separately proved construction project.
- [CI 39037098362](https://github.com/TruSudo/Construction-Sight/actions/runs/39037098362):
  **2,747 passed on Python 3.11 and 2,747 passed on Python 3.12**,
  two non-failing warnings each; strict Mypy and Ruff passed.
- [Command Center / USGS 39037098367](https://github.com/TruSudo/Construction-Sight/actions/runs/39037098367):
  both jobs passed, including exact native dossier finance lineage, existing
  source/watch/capture/SMARTS/commercial journeys, graph, map and all
  configured functional-contract checks. Pixel-perfect approved mockup parity
  and owner-device/live-source validation are still open.

**Latest historical outcome and calculated-share integrity parity:**

- The native source-candidate lineage now binds its original workflow to the
  **same bounded revision-aware validator used by the legacy result ledger**.
  The complete exact workflow/package/ledger identity and linear supersession
  chain are checked before displaying each original result. Only the latest
  revision is current. Earlier revisions are retained as corrections, not
  independently additive business or royalty outcomes.
- The latest and preceding historical revisions expose SHA-256 content digests,
  decision status, gross amounts in **integer cents**, share rates in exact
  millionths, and calculated share amounts in **integer cents**, without
  converting an estimate into authorization, entitlement, receivable or
  payment. The original ledger validator additionally checks every historical
  share receipt and exact stored monetary index, including *superseded* shares.
  Tampering with an older calculated share is rejected even if the current
  corrected result no longer contains a share.
- [CI 39035341740](https://github.com/TruSudo/Construction-Sight/actions/runs/39035341740):
  **2,747 tests passed on Python 3.11 and 2,747 on Python 3.12**, with two
  non-failing warnings on each; Ruff and strict Mypy passed.
- [Visual/USGS 39035341739](https://github.com/TruSudo/Construction-Sight/actions/runs/39035341739):
  both jobs passed, including the native original-financial-history browser
  journey, maps, investigation, and retained functional-contract checks.
  Exact approved-mockup pixel parity remains open.

**Latest exact-source approval audit and historical commercial candidate lineage:**

- A local source-replay approval now commits **atomically** with the queued
  investigation worker job in the existing immutable runtime-event database.
  The approval retains the exact original source SHA-256, deterministic native
  source/evidence identity, explicit confirmation and review reason. The worker
  checks that audit and refuses any replay that became stale or disagrees with
  the retained approved source. A read-only native audit view shows the current
  job state and its original review rationale. No named operator authentication
  or independently verified project identity is claimed.
- A bounded native commercial lineage view now locates retained original lead
  workflows **only** when their indexed base-candidate ID equals the original
  CEQA/permit source-candidate identity. It validates each persisted workflow
  and exact review package, shows historical workflow status and unverified
  outcome revision counts, and references a canonical investigation only when
  the current exact source observation is retained there. No source lineage
  establishes a same-project review, commercial authorization, share
  entitlement, paid royalty or valid contract.
- [CI 39033370170](https://github.com/TruSudo/Construction-Sight/actions/runs/39033370170):
  **2,746 passed on both Python 3.11 and Python 3.12**, two non-failing
  warnings each; both quality gates passed.
- [Browser/USGS 39033370114](https://github.com/TruSudo/Construction-Sight/actions/runs/39033370114):
  both jobs passed, including the new audit and candidate-lineage browser
  journey, existing commercial journeys, graph and mapping, and all configured
  functional-contract checks. Exact approved-mockup pixel parity remains open.

**Latest source-reconciliation and verified-export acceptance:**

- [CI 39029895949](https://github.com/TruSudo/Construction-Sight/actions/runs/39029895949):
  **2,744 passed on Python 3.11 and 2,744 passed on Python 3.12**;
  two non-failing warnings each. Both configured Python quality gates,
  strict Mypy, Ruff and dependency checks passed.
- [Browser/USGS 39029895923](https://github.com/TruSudo/Construction-Sight/actions/runs/39029895923):
  both jobs passed. New exact source replay and original verified ZIP download
  were exercised in the native browser. Existing graph, evidence, map, commercial,
  recovery and **33/33 functional actions and 33/33 complete contracts** remained
  green. The visual structure/fonts and recorded ratchet passed, while exact
  mockup pixel parity **did not**.

**Earlier accepted Phase 8 native source/commercial integration:**

- [CI 39026838373](https://github.com/TruSudo/Construction-Sight/actions/runs/39026838373):
  **2,741 passed on Python 3.11; 2,741 passed on Python 3.12**, with two
  non-failing warnings each. Ruff, strict Mypy and the other configured quality
  and dependency checks passed.
- [Browser/USGS 39026838378](https://github.com/TruSudo/Construction-Sight/actions/runs/39026838378):
  both jobs passed. The original SMARTS/CEQA/source-watch and no-send
  request/pricing/proposal native browser journey passed, as did preserved
  investigations, graph, map, backups, and **33/33 functional actions and
  33/33 complete workflow contracts**. Structural/font acceptance and recorded
  visual-ratchet checks passed. **Exact pixel parity failed** and is not claimed.

**Still open before Phase 8 acceptance / merge proposal:**

1. Establish complete retained scope migration/reassessment on the intended
   original records, using the now-tested bounded review/worker/rescan handoff.
   Native acceptance covers mixed-source scope traversal and genuine retained
   CEQA bytes; no owner-data migration or countywide completeness is claimed.
   The exact candidate
   lineage and durable replay reason are now accepted, but financial outcome,
   royalty and historical workflow transitions remain **separate original
   records**, not migrated canonical commercial state. Establish those links
   with independent source evidence and explicit review without fabricating
   same-project identity, payment or commercial authority.
2. Complete remaining historical original source/report/archive and investigation
   control equivalence. The CEQAnet chain-report ZIP pathway is retained and
   proven; original source-attribution aliases now reach the native registry,
   with sixteen original/native HTTP read contracts compared directly. This
   does not certify every historical CLI or authorize original-system retirement.
3. Close actual approved 1672 × 941 pixel discrepancies without redesigning the UI.
4. Reconfirm the owner-device Zorin deployment and permissioned real-source
   end-to-end field acceptance left open from Phases 3–4.

**Phase 8 is not complete.** No main merge, original-operator retirement,
live-source authorization, outreach transmission, binding bid or verified
sales outcome is claimed. Continue on draft PR #234 and do not merge without
the owner's explicit approval.

## Phase 7 — IMPLEMENTATION AND REGRESSION ACCEPTED

The following reconciles the controlling directive's assurance obligations for the
**currently integrated workflows**. It does not retire historical capabilities,
reuse an old certificate as current authority, accept the owner's deployment, or
substitute for Phase 8 feature parity.

Exact accepted application/test source: `3429b14f847163083dfdf32b181bc231d17605c6`; tree `16a6c2d65345b461e40977586f9aa7dc5009411e`. This acceptance-record update changes STATUS.md only.

Concrete completed repairs:
- Native bid/royalty operations now reuse private-file database preparation and enable/verify SQLite foreign keys. Symlinked or nonprivate workflow stores fail closed without changing the target file.
- Native royalty contracts are immutable at the database boundary. Ledger inserts require an existing contract; reads verify exact pinned bid versions, indexed identities, contract values, rates, calculations, entry kinds and original/reversal relationships. Backup/restore applies the same financial read validation without modifying the snapshot.
- Legacy share-model validation now uses decimal half-even math, matching existing scaled-integer calculation at half-cent boundaries. Legacy fractional inputs remain readable where previously supported; new-write precision guards remain unchanged.
- Restored the historical final-workflow/result compatibility rule in both the core result service and the authorized apply path. Final outcomes require the corresponding closed workflow, without implicitly granting a workflow transition. Positive correction tests now perform the actual recorded workflow transitions before recording final results.
- Retained evidence reads/references require the original content hash and agreement between indexed metadata and validated payload. A missing hash is never silently regenerated. New writes revalidate model copies. Inspecting a retained-input evidence record verifies its original bytes through the existing content-addressed input reader.

| Preserved guarantee | Enforced current path | Executable evidence |
| --- | --- | --- |
| Native/silent-risk assurance scope and historical defect evidence | Existing exact-tree/source/preflight certification retains its scope; historical certificates and branch evidence remain preserved, not treated as current runtime permission | `test_assurance_certification.py`, `test_assurance_preflight_certification.py`, `test_assurance_source_certification.py`, `test_assurance_reviewed_tree_binding.py` |
| Source access, source revisions, authorization and terminal access failures | Shared explicit-fact policy, exact review identity, immutable current checklist/registry binding, finite CEQA plan/effect scope, SMARTS failure stops | `test_access_policy.py`, `test_source_verifier.py`, `test_ceqanet_recurring_run.py`, `test_ceqanet_background.py`, acquisition/runtime regressions |
| Evidence provenance and source authority | Canonical evidence hash, indexed/payload agreement, exact retained input bytes; generic provenance and source claims do not self-verify | `test_provenance_authority.py`, `test_intelligence_store.py`, `test_phase7_assurance_acceptance.py`, `test_unified_assurance_reconciliation.py` |
| Identity resolution and uncertain cross-source membership | Existing artifact/parcel resolution; candidate-only common location; scoped human association; no automatic identity/commercial authority | `test_artifact_identity_resolution.py`, `test_derived_identity_integrity.py`, `test_investigation_multisource_acceptance.py`, `test_parcel_assurance.py` |
| Database integrity and transaction boundaries | Governed investigation schema/private connection, native private connection/FK enablement, atomic worker result/follow-up/completion, atomic outcome/head/event and native bid/feedback | `test_schema_governance.py`, `test_database_integrity.py`, `test_investigation_jobs.py`, `test_adversarial_semantic_witnesses.py`, Phase 7 acceptance |
| Immutable history, duplicate suppression, contradictions and temporal integrity | Existing evidence/event collision guards, immutable bid/contract/ledger rows, durable idempotent jobs, explicit review gaps and retained source-revision journal replay | `test_intelligence_store.py`, `test_investigation_runtime.py`, `test_investigation_assessment.py`, `test_command_center_live_graph.py`, browser graph journey |
| Recovery and rollback | Retained-input backup identity checks, read-only restore preview, independent worker restart/leases, protected request reservations and revocations outside rollback scope | `test_data_folder.py`, `test_investigation_runtime.py`, `test_investigation_jobs.py`, `test_ceqanet_background.py`, Phase 7 acceptance |
| Supply-chain and dependency integrity | Existing source-tree/supply-chain checks, pinned packages, strict dependency integrity and vulnerability CI gates; no dependency added | `test_supply_chain.py`, `test_supply_chain_source_tree.py`, complete CI |
| Financial integrity and authoritative results | Shared exact cents/rate units, decimal half-even model validation, stale-state and finality checks, immutable outcome revisions/head/event, pinned native contract terms and corrective reversals | `test_result_ledger_precision.py`, `test_result_ledger_supersession.py`, `test_result_authority_operator.py`, `test_result_authority_event_integrity.py`, `test_result_authority_apply_authorization.py`, Phase 7 acceptance |
| Outreach/bid authorization and investigation isolation | Loopback/origin-checked native local writes, separate user-entered commercial records, scope-bound legacy effects/request evidence; no sending or bid submission introduced | `test_bid_request_service.py`, `test_outreach_preview_service.py`, `test_unified_assurance_reconciliation.py`, native browser commercial journeys |

Historical test/evidence reconciliation (all original blobs/branches preserved):

| Missing historical test at the Phase 1 baseline | Disposition |
| --- | --- |
| `test_database_integrity.py` (`51eb5a80`) | Restored, extended to actual private investigation connections and native workflow private-file/FK boundary |
| `test_ceqanet_csv_export.py` (`59978b3c`) | Current `test_ceqanet_csv_contract.py` and `test_ceqanet_csv_live.py` cover exact project/document URLs, scope mismatch, parser/header limits, explicit execution, response/body/URL tampering and offline CLI; operator service tests add exact effect binding |
| `test_ceqanet_ingestion_inbox.py` (`fd04d786`) | Existing `test_operator_ingestion_inbox.py` retains the original read-only workflow; shared inbox/source/runtime and public-filing regressions prove automatic retained ingestion, canonical state and unchanged source bytes |
| `test_ceqanet_verified_source_maturity.py` (`a0bbe286`) | Historical dated registry/checklist/plan/audit evidence remains an archival certificate. Current maturity/access-policy/recurring-run/background tests enforce digest identity, reviewed evidence scope, expiry/current-state drift and blocked access; no historical verified label activates a current source |
| `test_result_ledger_authority.py` (`618b7116`) | Current immutable content-digest/revision/head/event services replace obsolete duplicate authority tables. Existing operator/event/supersession/CAS/rollback tests preserve history and stale-state rejection; Phase 7 restores the previously missing workflow-finality rule and proves rejection before authority/ledger writes |

Exact-source acceptance:
- [Full CI 39015279406](https://github.com/TruSudo/Construction-Sight/actions/runs/39015279406): **2,725 passed on Python 3.11 and 2,725 passed on Python 3.12**, two non-failing upstream Typer/Click warnings per leg. Ruff, strict Mypy (**347 source files**), JavaScript syntax, dependency integrity and dependency vulnerability audits passed; no known dependency vulnerabilities reported.
- Local Python 3.12: **2,725 passed**, two upstream warnings, **290.21s**. Focused native financial/data-folder/workflow, financial/result/public-source and final evidence/authority suites also passed; their overlapping counts are not added to the full regression count.
- [Browser/USGS 39015279426](https://github.com/TruSudo/Construction-Sight/actions/runs/39015279426): both jobs passed. **33/33 actions and 33/33 complete workflow contracts**, shared investigation/live graph continuity, native commercial and backup/restore journeys, structure/fonts and the reported visual ratchet passed. **Exact pixel parity did not pass and is not claimed**; Phase 8 must account for visual/functional parity separately.
- No active defects are declared in the retained current `governance/active_defects.toml`. Historical Native Maximum Assurance and silent-risk evidence retain their original scope; this acceptance is not a newly issued formal native-maximum certificate or a representation that old artifacts certify the current tree.

**Phase 7 development implementation/regression acceptance is complete.** All identified applicable safeguard gaps from the historical reconciliation are repaired or have a tested current equivalent, with historical assets and evidence preserved. Remaining source/device operational checks from Phases 3–4 are unchanged and still open. **Next: Phase 8 full functional-parity review**, including mandatory capabilities not yet proven equivalent in the approved native interface. No main merge, source activation, owner-device deployment, automatic outreach, bid submission or original-interface retirement is authorized by this status update.

## Phase 7 continuation — explicit facts and immutable access-review identity

- Restored the historical PR #155 access-fact guarantee in the current shared evaluator. All five restriction facts now default to unknown; each must be an actual Boolean. Unknown, numeric and text lookalikes require review. Known login/CAPTCHA/robots/terms/paywall restrictions remain blocking or review-required.
- An all-clear profile requires a lowercase `review:<sha256>` or `evidence:<sha256>` identity. Legacy reviewed flags and narrative fields remain accepted as caller metadata but cannot confer access. A correctly shaped identity is not independent proof of lawful source permission or proof that its supporting artifact exists.
- Listing, detail and CSV operator authorization state explicitly includes that identity. The existing recurring CEQA lane supplies its already checked current checklist digest; no review is synthesized from source reachability, a confirmation flag or a free-text statement. Current registry/checklist drift, finite plans, effect reservations and no-retry protections remain in place.
- Negative acceptance covers each unknown restriction before verifier/listing/detail/CSV transport, non-Boolean values, omitted facts, malformed/missing identities, and changed review identity against an existing immutable listing plan. Positive adapter/source/service fixtures now state all five facts and a deliberately synthetic review identity explicitly. Existing finite background/restart/revocation/rollback acceptance passed in the focused run.
- Exact-tree local Python 3.12 acceptance: **2,698 passed**, two upstream Typer/Click deprecation warnings, 317.11s. Focused acquisition/source/service/adapter/background and CLI compatibility tests also passed. Ruff, strict Mypy (347 source files), dependency integrity and JavaScript syntax passed. [Browser and USGS workflow](https://github.com/TruSudo/Construction-Sight/actions/runs/39011618658) passed on the exact source, including live graph continuity, **33/33 actions and 33/33 contracts**, structure/fonts and the reported visual ratchet. Exact pixel parity did not pass and is not claimed. [Dual-Python CI](https://github.com/TruSudo/Construction-Sight/actions/runs/39011618645) passed: **2,698 tests on Python 3.11 and 2,698 on Python 3.12**, two non-failing upstream warnings per leg; complete quality checks and dependency vulnerability audits passed with no known vulnerabilities. This document-only update preserves the exact validated application/test revision above.
- Phase 7 remains in progress: current-source gates passed; next complete historical financial/result-authority and retained-evidence reconciliation. No source activation, laptop installation, commercial action, main merge, historical retirement or complete safeguard-equivalence claim.

## Phase 7 continuation — source scope and database reconnection

- Recovered development head `8926ef8002cd7f8fdb5c88443209282a0e8abb45` already passed [full CI](https://github.com/TruSudo/Construction-Sight/actions/runs/38995303991) and [browser/USGS checks](https://github.com/TruSudo/Construction-Sight/actions/runs/38995303982). That checkpoint restores the historical foreign-key test and exercises retained bytes, distinct uncertain identities, commercial isolation, read-only native queries and duplicate-free worker replay through the shared runtime.
- The preserved `SourceVerifier.verify` API now refuses an access profile whose URL differs from the actual source before calling transport. Negative cases cover another host, another path, another scheme and another query. The unified CEQA background worker uses this class's response classifier, not its verification method; this fix does not certify the background lane or grant source authority.
- Extended the restored database regression to the actual private investigation engine: foreign keys remain enabled after disposing/reopening connections, and orphan verification inserts fail on each connection.
- Exact-tree local Python 3.12 acceptance: **2,650 passed**, two upstream Typer/Click deprecation warnings, 294.82s; focused source/database/native acceptance: **17 passed**. Ruff, strict Mypy (**347 source files**), JavaScript syntax and dependency integrity passed. [Browser/USGS workflow](https://github.com/TruSudo/Construction-Sight/actions/runs/39006641042) passed, including the shared live graph, native investigations, **33/33 actions and 33/33 contracts**, structure/fonts and the nonblocking visual ratchet. Exact pixel parity did not pass and is not claimed. [Current-source dual-Python CI](https://github.com/TruSudo/Construction-Sight/actions/runs/39006641023) passed on both Python 3.11 and 3.12: **2,650 tests each**, two non-failing upstream warnings per leg; full quality checks and dependency vulnerability audits passed (no known vulnerabilities).
- Prior-checkpoint finding (addressed by the explicit-facts continuation above): an explicitly unknown (`None`) CAPTCHA fact plus a reviewed flag and free-text basis currently returns `ALLOWED` from `evaluate_access`. No request was performed. Historical PR #155 (`42642d46`) rejects unknown facts and requires a `review:`/`evidence:` SHA-256 basis. Current background execution has additional checklist/plan checks; this reproduction alone does not prove those checks can be bypassed. Restore the applicable guarantee and verify every affected caller before acceptance.
- Phase 7 remains **in progress**. Next reconcile the historical digest-bound access-fact review against each applicable unified acquisition boundary, then remaining historical financial/result-authority and retained-evidence obligations. Existing tests and historical assets remain preserved; no full historical safeguard equivalence is claimed. Owner-device/live-source checks remain open.

## Phase 6 implementation acceptance — VERIFIED (not owner-device production acceptance)

**Exact validated application/source revision:** `5c03cd80cde497b2dfc0e3533a913000db280812`; existing draft PR #234.

- [Python full CI 38991749216](https://github.com/TruSudo/Construction-Sight/actions/runs/38991749216): **2,642 passed on Python 3.11** (316.25s) and **2,642 passed on Python 3.12** (308.88s); two non-failing Typer/Click warnings per leg. Ruff, strict Mypy, JavaScript syntax, dependency integrity and vulnerability checks passed.
- [Browser + live USGS 38991749140](https://github.com/TruSudo/Construction-Sight/actions/runs/38991749140): both workflow jobs successful; graph acceptance exercised exact retained source/date/confidence filters, independent background worker, embedded/full-screen single-canvas identity, committed event catch-up, reconnection, immutable evidence/dossiers, saved local views, source grouping and collapse, exact-anchored historical graph snapshots and comparison, return-to-live and **bidirectional** graph/Site Map navigation. Existing 33-action/33-contract functional parity workflow and visual/USGS observational checks passed; full reference-image pixel parity is not claimed.
- Historical state is rebuilt in memory from the existing immutable before/after graph revision journal, with exact sequence/event ID checks, bounded 12,000-event/10,000-record work, timeline pagination and explicit failure for missing/conflicting earlier revisions. Historical views are limited to complete *retained* revision chains; missing old records and past physical construction are never inferred. Historical view disables navigation into current dossiers/map coordinates to avoid time-travel ambiguity; live mode resumes the real worker event cursor.
- The five-family retained-data acceptance exercises CEQA, planning, permit, parcel and agenda evidence with deliberate human-reviewed contextual associations, source revisions and preserved prior snapshots. Tests preserve uncertainty, distinct source identity and no implied commercial approval. No new graph store, source/credential authority, outbound actions or database schema migration was introduced.
- Phase 6 **development implementation is accepted** against the controlling directive; external operation remains unaccepted until owner-Zorin installation, permissioned live-source collection and Phase 3/4 realistic field verification. Those conditions are not silently waived. Proceed to Phase 7 only in the original sequence, with no merge to main without authorization.

## Phase 6 controls and graph-to-map development acceptance — verified

**Exact accepted source:** `271ac23575fa55a3693d8a1ea6d203676db95a9f` on draft PR #234.

- [Full CI 38987482832](https://github.com/TruSudo/Construction-Sight/actions/runs/38987482832):
  Python **3.11: 2,640 passed** (two non-failing warnings);
  Python **3.12: 2,640 passed** (two non-failing warnings).
  Ruff, strict Mypy, JavaScript syntax, dependency integrity and vulnerability checks passed.
- [Command Center and live USGS 38987482794](https://github.com/TruSudo/Construction-Sight/actions/runs/38987482794):
  both workflow jobs successful. The real browser's extended Phase 6 journey checked
  source-family filtering against authoritative edge families, future-date exclusion,
  evidence-node collapse, named saved-layout/filter restore, exact node identity
  preservation after node-kind arrangement, and navigation to the existing Site Map
  centered on retained, source-claimed dossier coordinates. Earlier shared canvas,
  evidence inspector, dossier, independent worker and reconnect tests remain passing.
- The graph API now exposes exact persisted source-family, date-basis and timestamp
  details for retained nodes/edges with recorded assertion confidence. Client
  display filters do not alter the intelligence store or verify construction/identity.
  Saved layout coordinates and filters are confined to the local browser; no source
  evidence or inferred relationship is stored there. Unmapped canonical investigations
  do not receive invented coordinates or map pins.
- **Remaining Phase 6:** reconstruct historically faithful graph state as of a retained
  revision (separate from paged activity events), broader evidence-aware clustering,
  and complete realistically retained cross-source acceptance. No laptop deployment,
  live jurisdictional permission/collection acceptance, source activation, outreach,
  bid submission, main merge or legacy-interface retirement.
- This document-only checkpoint follows the exact CI-certified source and does not
  change application or test code.

## Phase 6 first-slice acceptance — verified, Phase 6 still partial

**Source:** `db525989acec562637a329e6dc9de93b73e04cd3`.

- [CI 38985087688](https://github.com/TruSudo/Construction-Sight/actions/runs/38985087688):
  Python 3.11 **2,639 passed**, two non-failing warnings, 287.05s;
  Python 3.12 **2,639 passed**, two non-failing warnings, 294.10s.
  Ruff, strict Mypy (346 source files), JavaScript validation, dependency integrity
  and vulnerability auditing passed; no known dependency vulnerabilities reported.
- [Browser/visual 38985087540](https://github.com/TruSudo/Construction-Sight/actions/runs/38985087540):
  both jobs successful. The new live graph journey passed shared embedded/expanded
  canvas identity, canonical dossier and exact retained evidence inspection,
  independent worker advancement while paused/closed, committed event delivery,
  unique node IDs, disconnection recovery and reopen reconstruction.
  Existing five-view investigation journey and **33/33 actions / 33/33 contracts** passed.
- Desktop structure/fonts and the reported non-blocking pixel ratchet passed.
  Absolute pixel parity did not pass and is not claimed.
- Demonstrations used deliberately synthetic retained fixtures and real worker processes;
  this is not owner-device deployment or authorized real-source operational acceptance.
- Next: historical graph-state replay using retained before/after revisions, saved
  investigation layouts/views, remaining source/date/confidence controls, clustering,
  collapse, optional actual-activity highlighting and complete graph/map/review acceptance.
  Preserve the same event-backed engine for embedded and full-screen modes.

## Phase 5 development acceptance — verified

**Accepted source:** `44e80090219a0ad0938dbec44848233d089bcf2d`.

- [Full CI 38983505421](https://github.com/TruSudo/Construction-Sight/actions/runs/38983505421):
  Python 3.11 **2,635 passed**, two non-failing warnings, 221.05s;
  Python 3.12 **2,635 passed**, two non-failing warnings, 221.93s.
  Ruff, strict Mypy (345 source files), JavaScript checks, dependency integrity and
  vulnerability auditing passed; no known dependency vulnerabilities reported.
- [Browser/visual 38983505583](https://github.com/TruSudo/Construction-Sight/actions/runs/38983505583):
  native shared-investigation journey passed, existing **33/33 actions and 33/33 contracts**
  passed, independent worker source-revision publication and dossier refresh passed,
  refresh failure/manual recovery passed, source/location filtering, canonical-ID
  consistency, unmapped handling, global party search and persisted entity/evidence
  inspection passed. Live USGS observational probe passed.
- Approved desktop structure/fonts and reported non-blocking pixel ratchet passed.
  Absolute pixel matching did **not** pass and is not claimed; no pixel gate was weakened.
- LIVE (controlled retained-fixture runtime): five native workspaces consume canonical
  investigations, retained evidence and actual worker revisions without reload.
- INTEGRATED: Site Map, Lead Console, Project Intelligence, Evidence Chains, dossiers,
  Entity Network, bounded shared search/filtering, region choices and revision refresh.
- ASSURANCE: owner-only/read-only existing-store access, preserved IDs/lineage, bounded
  requests, continuation for nonmatching scan pages, late-response/disposed-view guards,
  uncertainty and commercial-authorization boundaries remain enforced and tested.
- PARTIAL: owner-device systemd deployment and permissioned real-source operational
  acquisition/acceptance from Phases 3–4 remain open. Retained browser fixture data are
  deliberately synthetic. This is Phase 5 development acceptance, not production/live-source
  certification, Phase 6 graph acceptance, historical assurance completion or full parity.
- NEXT: Phase 6 live Relationship Graph in embedded and expandable full-screen
  VirusTotal Threat Graph-style modes over the same durable events/state.

## Phase checkpoint

| Phase | Evidence-backed state |
| --- | --- |
| 1 — preservation/capability audit | Baseline inventory established; functional-equivalence and assurance obligations remain recorded below |
| 2 — shared foundation | SMARTS, CEQA, permit, parcel, planning, agenda, document and universal-intake contracts reach common persistence; dossiers, guarded reviews and canonical inventory implemented |
| 3 — background orchestration | SMARTS/inbox/timers connected; separately reviewed finite CEQA background lane implemented; real-source activation and owner-device deployment remain unaccepted |
| 4 — cooperating-source journey | Controlled and retained public-excerpt implementation acceptance exists; live-source operational acceptance remains open |
| 5 — native integration | Development acceptance complete at 44e80090; full Python and browser gates passed; operational field checks remain open under Phases 3–4 |
| 6 — live Relationship Graph | Development acceptance complete at `5c03cd80`; persisted live graph, full before/after revision replay, event-cursor recovery, saved layouts, filters, source grouping, activity highlighting, dossier/evidence inspection and bidirectional Site Map navigation validated by full CI and browser tests |
| 7 — assurance completion | Implementation/regression acceptance complete at `3429b14f`; historical safeguard/test reconciliation, financial/result authority and evidence integrity repairs passed full dual-Python and browser gates; operational field acceptance remains open under Phases 3–4 |
| 8 — functional parity | No complete parity acceptance; original interface retained |

## Operational evidence and integration

- Existing `IntelligenceStore`, graph/revision services, artifact resolution, intake,
  contractor assessment, parcel/site resolution and local review authorization are reused.
  There is no competing matching engine, new dependency or database-schema change.
- Source identities remain distinct. Common parcel/address produces review candidates,
  never verified project identity. Reviewed associations/rejections preserve source IDs;
  revised evidence triggers reassessment without silently reversing reviewed decisions.
- Dossiers distinguish certainty, identity, completeness, activity and readiness. Current
  construction and commercial authority remain unknown unless separately established.
- Canonical inventory uses bounded cursor pagination, suppresses reviewed aliases and
  retains unmapped records. Read-only inventory/dossier CLI checks preserve database bytes.
- Source-party contractor assessments remain unverified source claims. Intake matching
  excludes ambiguous/inferred facts and recomputes anchors from original values.
- Jobs use the existing immutable event store. Findings, follow-up jobs and completion
  share one transaction. Dependencies, bounded batches, replay suppression, controlled
  retries, expiring leases, stale-worker rejection and restart recovery are implemented.
- Original input bytes are retained before normalization. SMARTS polling retains exact
  validated responses and checks the lineage of the committed journal cursor.
- Site arrivals schedule parcel assessment from committed parcel inputs. Parcel arrivals
  schedule same-county reassessment independently of project matching. Both arrival
  orders pass controlled tests. Bounded parcel pools remain explicitly incomplete.
- Backup/restore includes content-addressed inputs, verifies their identities and resumes
  queued work. Refreshing inputs after database snapshots covers jobs queued during backup.
- CLI: `python -m constructionsight.investigation_runtime --data-dir PRIVATE_DIR`
  followed by `enqueue`, `run`, `status` or `units`. `units` previews independent systemd
  worker/timer units without creating state. No timer is installed or enabled here.
- Failed worker jobs are retained and produce a nonzero CLI run result.

**Retained-data demonstrations:** the prior SMARTS replay incorporated ten observations
into ten investigations, ten source nodes, ten evidence records and ninety events;
replay preserved counts. Original journal digest:
`0f64415f983c136bdb7621ae52b1977b269ae9ea2e15b3c4f36f7a17b80d000f`.
The canonical inventory reads twelve retained SMARTS/CEQA investigations. The latest
worker demonstration processes two genuine retained CEQA records through five jobs:
one ingestion, two correlation jobs and two parcel assessments. It preserves two
investigations and one review candidate. Empty local parcel evidence produces honest
no-match assessments. Original export bytes are unchanged and replay is idle.
These demonstrations do not establish verified sites, current activity or complete
cross-source investigation. No network acquisition was performed.

## Preservation and unresolved historical safeguards

[Audit evidence](docs/audits/unification-preservation-baseline-2026-10-16.json) retains
193 baseline remote tips (110 main ancestors, 83 unique contributions), all 333 baseline
Python modules, contributed runtime/test/evidence paths and native/legacy import
reachability. File ancestry/imports are not functional proof. No historical assets discarded.

- Verified archives: `archive/pre-pass-a-2026-10-15` at `7771e7d`,
  `archive/silent-risk-e47e335` at `e47e335`, `archive/silent-risk-e49cca5` at `e49cca5`.
- Native assurance `10037faa` and silent-risk certification are ancestors;
  native-assurance `3e11e27` retains two unique commits.
- Required PRs #143/#155/#158/#186/#193/#195/#232/#233 were checked and remain
  open/unmerged at the audit baseline. #232/#233 retain six/twelve commits beyond main.
- Preliminary unified branch `86bfc264` retains sixteen commits beyond main. Its
  read-only aggregation is not the required engine; its defective whitespace matcher
  was not adopted.
- Eight historical production paths are absent from main: three CSV exporters,
  `money.py`, three result-ledger-authority modules and the preliminary bridge.
  Current counterparts and exact gaps are indexed. Five test paths, one patch script,
  25 assurance evidence paths and one closure proof remain branch-retained.
- Historical access-basis gap is reconciled in the development runtime: explicit restriction facts and immutable review/evidence identities are required; current scope/state checks remain enforced. Main is unchanged.
- Native money uses Decimal/integer cents; older ledger models retain float fields.
  Complete financial/workflow equivalence remains unproven.
- Current SQLite connections enforce foreign keys; Phase 7 restored the historical test path and added private-engine reconnection/orphan-insert acceptance.
- Original operator UI remains preserved. Approved native design is unchanged by this
  backend continuation; absolute pixel parity is not claimed.

## Verification

- Earlier full regression before the last worker additions: **2,567 passed**, two
  upstream Typer/Click deprecation warnings, **663.78s**.
- Prior foundation-tree Python 3.12.14 full regression: **2,571 passed**, two upstream
  Typer/Click deprecation warnings, **595.59s**. This covers implementation `ff35100`;
  the subsequent checkpoint update changes only this status file.
- Focused foundation/source/site-resolution/database checks: 49 passed, two upstream
  warnings, 55.77s. Existing backup/schedule checks: five passed, 2.43s.
- Worker checks cover concurrency, dependencies, restart, stale leases, bounded retry,
  rollback, exact-byte tampering, bounded continuation, SMARTS cursor, backup/restore,
  concurrent enqueue during backup and CLI failure reporting. Both parcel-arrival
  orders passed separately (two cases, 6.72s).
- Ruff passed; strict Mypy passed for 341 modules; JavaScript syntax and pip check passed.
- Prior acquisition source checkpoint `b370621` passed Python 3.11/3.12 CI, browser/visual
  workflow and dependency vulnerability audits. Complete final integration and functional
  parity remain unaccepted. No merge readiness claimed.

## Next immediately executable task

The published finite CEQA background lane passed full CI and browser validation.
Real-source operation still requires an exact current source review and explicit plan
activation; no CEQA plan or owner-device timer is enabled here. Complete operational
Phase 3 acceptance with the realistic multi-source journey, without skipping safeguards.
Then complete the Phase 4 realistic cooperating-source investigation before migrating
native views (5), live graph (6), assurance completion (7) and functional parity (8).
Do not mark any phase complete merely because its files or tests exist.


## Acquisition/scheduling continuation — 2026-10-16

**LIVE / INTEGRATED:** Successful native SMARTS collection now queues retained journal
observations into the common engine. Scheduled capture drains a bounded worker turn;
the independent worker polls journal changes and an explicitly populated private
`investigation-inbox/<kind>/*.json`. Source kinds include the existing typed records
and `ceqa-csv-execution`, which independently replays actual retained CSV execution
bytes through the existing bridge and binds original plus normalized input lineage.
Inbox cursors are restart-safe; invalid files are retained/reported and do not starve
later inputs. Duplicate polls do not create graph activity or duplicate jobs.

**ASSURANCE:** Capture and processing outcomes remain separate. Successful worker
recovery clears stale handoff warnings only for the corresponding source capture.
Missing comparable artifacts are an unresolved correlation outcome, not a failed job.
Actual SMARTS 403 responses now raise a typed terminal denial, persist source disablement
and stop later scheduled/native retries until explicit re-enablement. The previous
scheduler only recognized an HTTP-library error string, while SMARTS used its own error.
Symlinked inbox files/directories are rejected without following external inputs.

**SCHEDULING:** The existing reviewed schedule digest covers all four capture/worker
service and timer units; the scheduling dialog displays all four. Stale review digests
are rejected. Installation failure attempts to disable both timers; disable handles
both. Worker status and failures are visible through existing schedule status. Tests
use isolated fake systemd managers; no owner-device units have been installed/enabled.

**TESTS:** 81 focused acquisition/API/schedule/investigation/runtime/native checks passed
in 62.49s. Ruff passed; strict Mypy passed for 342 modules. JS syntax and pip check passed.
The local acquisition-tree full regression passed (2,580 tests, two upstream warnings,
541.52s); final-source CI adds the activation test and passes 2,581 on each Python version.
Local Chromium is absent and its normal
Playwright download returned invalid/truncated archive data, so no local browser pass
is claimed. The existing GitHub visual workflow runs `tests/ui/schedule.js`, now checking
that both worker units are visible during review. Current published source `b370621` passed the browser/visual workflow, including the
expanded four-unit schedule review. This is CI browser proof, not a local browser pass.

**HISTORICAL CHECKPOINT:** CEQA's exact manual request allowances explicitly deny
background recurrence; no timer or inbox grants network permission or bypasses those
rules. Finish Phase 3 by implementing a separately scoped, reviewed CEQA background
acquisition capability using existing source checks, bounded plans, revocation and
durable effect allowances. Then prove the complete Phase 4 cooperating-source journey
before native-view migration, live graph and final assurance/parity acceptance.


### Final acquisition checkpoint verification

- `281b3e3` / published `3e281f8`: acquisition, inbox and scheduling integration;
  local Python 3.12 regression: **2,580 passed**, two upstream warnings, **541.52s**.
- `0e18db9` / published `b370621`: final two-line activation rollback plus its
  controlled failure case. Updated acquisition/scheduling set: **13 passed**, 13.26s.
- Published current tree: `11505f2da148cb5c4950811491be23edc954345c`, verified identical to local `0e18db9`.
- Current browser/visual workflow passed; its Daily schedule integration step passed.
- Current source CI: **Python 3.12: 2,581 passed**, two warnings, **199.00s**;
  **Python 3.11: 2,581 passed**, two warnings, **203.79s**. Both quality jobs passed,
  including Ruff, strict Mypy, JS syntax, pip check and dependency vulnerability audits.
  CI run: `38939767419`; visual/browser run: `38939767402`. The two warnings are
  upstream Typer/Click deprecations. Subsequent status-only edits do not change source code.


## Finite CEQA background continuation — 2026-10-16

A separate `ceqanet_background` capability builds and previews up to 31 exact daily
listing windows. Enabling requires the exact plan digest and explicit background
confirmation. Its source definition, live registry/checklist identities, expiry,
execution limits and approval are bound together. The manual CEQA facade and its
no-recurrence restriction are unchanged. No real source request or activation was
performed during this implementation.

Each window permits one bounded CS-NET-002 GET page, at most 50,000 bytes and 20 seconds,
with no redirects, credentials, downloads or automatic network retries. Actual captures
remain at least 24 hours apart; old windows are skipped rather than fetched in a burst.
This is bounded partial discovery, not complete CEQA coverage. Generic provenance
remains unverified; missing county/location is not inferred from search filters.
Distinct captured documents/revisions preserve separate source record identities.

The independent worker's `--poll-ceqa` hook is dormant without a reviewed enabled plan.
Exact original execution artifacts are retained before normalization and linked to
shared-engine jobs. Retained result handoffs recover after restart or revocation.
Access failures, CAPTCHA/login/paywall warnings, truncation, transport errors and
ambiguous interrupted attempts stop further requests. Invalid acquisition configuration
does not prevent unrelated retained jobs from progressing. Worker failures surface in
the existing schedule warning. The reviewed timer digest includes the changed command;
the native review explicitly distinguishes CEQA plan approval from timer installation.

Existing authorization, protected-effect consumption, bounded listing executor,
verification, result parser and persistence preview are reused. Durable request
reservations, approvals and stop/revocation receipts survive observation-backup rollback;
copied data directories do not inherit an operative grant. Original local files and
historical functions remain preserved. No dependency or database-schema change.

Operator entry point: `python -m constructionsight.ceqanet_background --data-dir DIR`
with `build`, `preview`, `enable` or `revoke`. `build` accepts a reviewed one-page
`--definition`, current `--registry` and `--checklist`, timezone-aware `--first-due`
and `--days` (1–31). `enable --plan FILE --approved-digest SHA --confirm-background`
records a separate finite approval and performs no network request. The existing
investigation worker then handles only due approved windows.

Validation: 65 focused background/acquisition/runtime/manual-CEQA/scheduling tests
passed in 32.77s, including 25 new background cases. Ruff, strict Mypy (343 modules),
JS syntax and pip check passed. Current published source `ed35d7a` passed full CI: Python 3.12 **2,606 passed**,
two warnings, **229.36s**; Python 3.11 **2,606 passed**, two warnings, **276.14s**.
Both complete quality gates and dependency vulnerability audits passed. The
browser/visual workflow passed, including the updated four-unit review and explicit
separate CEQA approval scope. Absolute pixel parity is not claimed.
CI run: `38948226703`; browser/visual run: `38948226682`.
Earlier 2,581-test CI results above describe the preceding source tree.
Native-view migration, live graph delivery/UI, full historical assurance reconciliation
and complete functional parity remain outstanding; no main merge or deployment.

## Phase 3 independent-worker recovery continuation — 2026-10-16

SMARTS journal/capture metadata failures and inbox cursor/directory failures now report
separate intake failures while allowing unrelated retained jobs to progress. A failed
SMARTS poll is attempted once per worker turn; source bytes and committed cursor remain
unchanged. CLI and scheduled capture return failure for unsuccessful intake instead of
reporting the whole turn as successful. Independent last-poll receipts keep the existing
schedule warning visible across retained-only turns until that lane is polled successfully.
These are offline processing retries, not new network acquisition authority.

The genuine retained CEQA CSV execution also passed a standalone process-boundary journey:
one worker automatically discovers the inbox input and executes one ingestion job;
a fresh worker completes four dependent jobs; a third is idle without duplicate events.
Two investigations remain unmapped and unverified, with exact original execution bytes
retained. No dashboard, live CEQA request, enabled plan or installed timer is involved.

Validation: **71 focused tests passed in 38.92s**, including five new recovery/process
cases. Ruff over src/tests, strict Mypy over 343 modules and dependency integrity passed.
Current complete Python 3.11/3.12 CI remains pending publication of this change; the
2,606-test results above belong to the preceding source tree. Phase 3 live source and
owner-device acceptance remain outstanding. Finish the concrete current source review,
finite-plan activation review and deployment acceptance before declaring Phase 3 complete.
Continue with Phase 4 only after that acceptance; no main merge or historical retirement.


## Phase 5 — Site Map and Lead Console acceptance continuation

The native map and Lead Console already consume canonical investigation inventory at
`9e0e839d6f212268f9d1b8fdf5ce36b12a92bf74`; that exact head passed both CI workflows.
This continuation fixes investigation coverage being overwritten by lead-only map
counts and includes source-claimed investigation coordinates in Site Map fit bounds.
The browser fixture retains one mapped and one unmapped independent investigation;
expanded browser acceptance checks canonical IDs across four views, keyboard marker
to dossier navigation, coverage counts and absence of these markers in the overview.
No real project coordinates are created by this synthetic test fixture.

Local checks: both changed JavaScript files pass Node syntax validation; Python fixture
compiles; execution of actual drawMap with controlled DOM stubs passes mapped/unmapped
coverage and overview-isolation assertions. Full Python and Playwright CI on this new
source is pending. These local checks are not a browser or live-source acceptance.

Next: finish Entity Network, unified filtering/search, revision-driven refresh and
cross-view acceptance. Phase 3 owner-device/source operational verification and Phase 4
live end-to-end acceptance remain open; Phase 5 is not complete. Main unchanged.


## Phase 5 implementation notes — before final acceptance

Shared investigation inventory now supports bounded retained-text/party, source-family,
county, source-claimed city and mapped/unmapped filters. Scan cursors remain available
even when a filtered page has no matches; totals are explicitly all-scope totals.
A cheap read-only revision query drives bounded five-second refresh of active native
views. Detached views stop polling, overlapping and late responses are discarded,
failures mark the retained display stale, and an open investigation dossier follows
the same committed revision without promoting source claims.

Entity Network now exposes persisted canonical investigation/source/party/candidate
identities and original relationship/evidence IDs from the shared dossier, alongside
the preserved commercial source view. Candidate edges remain uncertain; rejected,
stale and superseded edges are excluded from the current network. Global search can
find retained investigations and parties, with explicit bounded-search continuation.
Dossiers expose retained artifact content/digests/limitations and discrepancy/candidate
details. All five native views use the same inventory/filter contract. Commercial
filters and actions retain their existing authority; unassessed investigations are
not automatically added to outreach or bids.

Local verification: three focused HTTP/query acceptance tests pass (2.57s), covering
read-only bytes, absent/unsafe store handling, filter validation, nonmatching first-page
continuation, same-identity revision and revision cursor advancement. Strict Mypy passes
for the three affected source modules with silent imported-module traversal. Ruff and
changed JavaScript syntax pass. Expanded Playwright acceptance covers five-view IDs,
map/dossier keyboard navigation, mapped/unmapped/source filters, persisted developer
relationships, global party search and an actual separate-worker source revision
reaching the open inventory/dossier without reload. Exact-source full CI/browser
results are pending, so Phase 5 acceptance is not yet asserted.

Phase 3 owner-Zorin deployment and permitted live-source operation, Phase 4 live-source
operational acceptance, Phase 6 live Relationship Graph delivery/replay/full-screen
interaction, Phase 7 historical assurance reconciliation and Phase 8 parity remain open.
No main merge, source activation, owner-device changes or commercial submissions.


## Historical recovery checkpoints

- Local branch: `agent/unification-continuation-2026-10-16`.
- Latest implementation commit: `c7c6741` (separately reviewed finite CEQA background acquisition).
- Prior acquisition implementation: `0e18db9` (SMARTS/inbox/timers and activation rollback).
- Earlier continuation commits: `0c92c2e` (remaining producers/inventory), `8dbbc82`
  (durable worker/recovery), `c28c577` (concurrent backup and CLI failure reporting).
- Published implementation / draft PR #234: `ed35d7a59dc36287692ebcb14b7401404da3366a`.
- Exact implementation tree: `779c4411499cc1bd93e2748062c8243baa347609`;
  verified identical to preserved local `c7c67419f69b7a181a8c396c4b2bf820a0fa62ca`.
- Source CI: 2,606 passed on each Python 3.11/3.12; quality gates, dependency
  vulnerability audits and the browser/visual workflow passed. Subsequent checkpoint
  documentation does not change source code.
- Main baseline: `4c8f8eaf08653e2d571b0df821b862dcc9b158ac`.
- Owner explicitly authorized publication on 2026-10-16. The connected GitHub
  publication commit `67e1e99` has the exact tested tree of local checkpoint `75d4217`:
  `71ab0138e047470961d4be87d92f3066831e8472`. Original local commits are preserved.
  The later acquisition publication `b370621` exactly matches local `0e18db9`.
  Its browser/visual workflow passed, including the reviewed timer dialog; both
  Python 3.11/3.12 quality gates and dependency vulnerability audits passed. No new owner approval is required
  for ordinary continuation/publication on this development branch.
- No main merge, branch deletion, history rewrite, original-UI retirement, expanded
  source authorization, automated commercial action or owner-device deployment.
- After any interruption, check `git status` and `git rev-parse HEAD` on this branch.



## Phase 6 — first-slice implementation notes before final CI

The existing private read-only store now supplies a bounded graph snapshot, explicit
retained evidence references, and cursor/anchor-validated durable event pages. Snapshot
and high-water mark share a SQLite read transaction; graph roots, entities, relationships
and evidence are retained identities, never browser-created matches. Rejected/stale/
superseded edges are excluded. A changed/missing journal anchor requires snapshot reset,
including backup/restore divergence. Events are compact and bounded; raw evidence is
loaded only when explicitly inspected.

Native Entity Network now opens a live embedded Relationship Graph with an expandable
full-screen interface over the same canvas/state. The charcoal-and-amber graph includes
a bounded force layout, zoom/pan/node dragging, node search, relationship-status filtering,
depth/root expansion of indexed state, keyboard node/edge inspection, canonical dossier
and retained-evidence inspection, pause/resume, connection status and actual persisted
worker activity. Pausing/closing affects the display only. Event delivery is bounded
1.5-second local read polling, chosen to reuse the localhost HTTP server and immutable
journal without persistent network authority or a new database. Snapshot revisions and
event delivery cursors remain separate so paged catch-up cannot skip journal events.

Seven focused graph/native-bridge tests passed in 4.44s: absent/unsafe store, stable IDs,
read-only bytes, worker revision, idle replay, anchor mismatch/reset, multi-page event
replay, rejected-edge removal, evidence HTTP inspection and exclusion of uncommitted
state. Ruff, changed-JavaScript syntax and strict focused Mypy passed. Exact-source full
CI and browser acceptance are pending. Browser journey checks embedded/full-screen
canvas identity, canonical dossier/evidence, worker progression while paused/closed,
committed event delivery, duplicate suppression and disconnection recovery.

Phase 6 remains PARTIAL. Historical graph-state replay (distinct from event-page replay),
saved investigation layouts/views, chronology/source/confidence controls, clustering,
node collapse, optional activity highlighting, reviewed research task submission,
full map navigation and the complete realistic retained-data acceptance remain open.
This slice does not certify Phase 6 or substitute for Phase 3/4 live-source/device checks.
Main unchanged; no source acquisition/activation, outreach, bids or historical retirement.
