# ConstructionSight — system unification

**Controlling assignment:** [owner's verbatim directive](docs/CONSTRUCTIONSIGHT_UNIFICATION_DIRECTIVE.txt).
Follow Phases 1–8 in order. Preserve mandatory historical functionality and safeguards.
One shared investigation engine, the approved native Command Center and a live
Relationship Graph remain the goal. Full unification and functional parity are not complete.

## Exact recovery checkpoint

- Development branch: `agent/unification-implementation-2026-10-16`, draft PR #234. Latest accepted Phase 7 application/test source: `3429b14f847163083dfdf32b181bc231d17605c6` (tree `16a6c2d65345b461e40977586f9aa7dc5009411e`).
- Latest source accepted for Phase 6: `5c03cd80cde497b2dfc0e3533a913000db280812` (anchored historical snapshots, retained-history timeline/comparison, saved layouts, source/date/confidence controls, source grouping, activity highlighting, and bidirectional graph/map navigation). Phase 5 remains pinned to `44e80090219a0ad0938dbec44848233d089bcf2d`.
- **Phase 7 implementation and regression acceptance is complete** for the controlling directive and currently integrated runtime. The final reconciliation and exact-source results below supersede the older continuation checkpoints. Phase 8 is now in progress; preserve the original interface and all historical assets.
- Phase 5 native integration is implemented. Exact-source acceptance results are recorded below.
- Main remains `4c8f8eaf08653e2d571b0df821b862dcc9b158ac`; no merge or owner-device/source activation.
- Phase 6 implementation acceptance is complete for the controlling Phase 6 directive: the same persisted investigation graph and committed worker events drive embedded/full-screen views, bounded anchored historical replay, connection recovery, dossiers and bidirectional map navigation. Phase 7 safeguard reconciliation is now accepted below; next follow the unchanged directive into Phase 8, without claiming real-source/device operational acceptance.
- Operational checks still open: owner-Zorin/systemd deployment, permissioned live-source background acquisition, and real live cooperating-source acceptance from Phases 3–4.
- Preserve all original interfaces, historical branches and assurance evidence through Phase 8 acceptance.

## Phase 8 — IN PROGRESS: native association review

Initial parity comparison uses the preserved operator routes/services and Phase 1
capability baseline. Passing regression tests does not establish native feature parity.
The original operator interface and historical assets remain intact.

| Capability | Native integration / parity finding | Remaining work |
| --- | --- | --- |
| Shared investigation inventory, dossiers, evidence, map and live/historical graph | Existing native views query the governed investigation state; prior Phase 5/6 acceptance is retained | Compare all original footprint, timeline and entity-query controls/exports against native equivalents |
| Human review of uncertain source associations | This slice connects the existing evidence-bound review service to native dossiers: inspect both source records/evidence, explicitly associate/reject, download receipt and reassess changed evidence | Complete browser acceptance below; broader parcel/source-review workflows remain separate |
| Source registry and source revision inspection | Original `/api/source-registry` and `/api/source-revision` remain preserved; native Sources & Collection has SMARTS collection/scheduling and separate reviewed CEQA background controls | Integrate the existing governed registry/revision projection into the native source workspace; prove equivalent inspection |
| Parcel and source-review queues | Original SMARTS parcel candidates, parcel candidates, candidate preview and source-review queue services remain available | Native equivalents are not yet demonstrated; reuse existing resolution/review boundaries |
| Capture queue, ingestion inbox and operator exports | Original capture queue/inbox/package capabilities remain; shared retained-input processing and native dossier JSON export cover part of the workflow | Compare queue inspection, retained capture handling and report/archive exports; implement missing native actions |
| Watchlists and monitoring | Native lead watchlist and original CEQA/permit source watchlist use distinct existing boundaries | Preserve source-specific watch/archive behavior and prove investigation monitoring parity |
| Commercial workflows/results | Native versioned bid/royalty operations and legacy authoritative workflow/result services retain their safeguards | Native commercial screens are not yet proven equivalent to legacy workflow/result, request-evidence and preview/draft capabilities |
| Approved visual design | New controls are confined to existing dossier dialogs, with scoped review styles; overview structure is retained | Exact pixel parity remains unaccepted; retain calibrated structure/font/pixel reporting |

Implementation: preview and write reuse `InvestigationReviewService` over the existing
private investigation store. Preview is read-only and binds both displayed source
contexts to current state. Writes require strict input, explicit confirmation and a
reason, and retain the service's stale-state, immutable audit and protected-effect
checks. Local Host/Origin checks and the maintenance lock still apply. Association
changes shared canonical inventory/graph context; rejection restores separate views.
Neither decision verifies project identity or grants commercial authority. Retained
source bytes remain unchanged. A failed/disconnected submission requires a fresh
preview and new confirmation, with no automatic retry. Late preview responses cannot
replace another open dialog. Multiline validation errors are flattened before entering
HTTP status headers, repairing a failure exposed by negative endpoint tests.

Verification: nine focused native review tests passed, including unchanged preview
bytes, strict/overbroad payload rejection, cross-origin rejection, missing-store
noncreation, association/rejection agreement and worker-revision invalidation. Full
regression and the new browser journey are pending on this source checkpoint. The
browser journey covers explicit confirmation, reassessment, late-dialog responses,
shared graph agreement and dialog bounds at the approved 1672×941 viewport.

**Phase 8 is not complete.** Next integrate governed source registry/revision inspection,
then resolve the remaining native parity gaps above. Earlier source/device operational
checks remain open. No main merge, original-interface retirement, live-source activation,
owner-device deployment, outreach or bid submission has occurred.

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
