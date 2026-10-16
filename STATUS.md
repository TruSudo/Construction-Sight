# ConstructionSight — system unification

**Controlling assignment:** [owner's verbatim directive](docs/CONSTRUCTIONSIGHT_UNIFICATION_DIRECTIVE.txt).
Follow Phases 1–8 in order. Preserve mandatory historical functionality and safeguards.
One shared investigation engine, the approved native Command Center and a live
Relationship Graph remain the goal. Full unification and functional parity are not complete.

## Exact recovery checkpoint

- Local branch: `agent/unification-continuation-2026-10-16`.
- Latest implementation commit: `ff35100` (automatic parcel reassessment).
- Earlier continuation commits: `0c92c2e` (remaining producers/inventory), `8dbbc82`
  (durable worker/recovery), `c28c577` (concurrent backup and CLI failure reporting).
- Published implementation / draft PR #234: `67e1e99b93a3e6da15ba473c6d5c8988448854fe`.
- Main baseline: `4c8f8eaf08653e2d571b0df821b862dcc9b158ac`.
- Owner explicitly authorized publication on 2026-10-16. The connected GitHub
  publication commit `67e1e99` has the exact tested tree of local checkpoint `75d4217`:
  `71ab0138e047470961d4be87d92f3066831e8472`. Original local commits are preserved.
  A subsequent status-only publication records this mapping; CI is pending.
- No main merge, branch deletion, history rewrite, original-UI retirement, expanded
  source authorization, automated commercial action or owner-device deployment.
- After any interruption, check `git status` and `git rev-parse HEAD` on this branch.

## Phase checkpoint

| Phase | Evidence-backed state |
| --- | --- |
| 1 — preservation/capability audit | Baseline inventory established; functional-equivalence and assurance obligations remain recorded below |
| 2 — shared foundation | SMARTS, CEQA, permit, parcel, planning, agenda, document and universal-intake contracts reach common persistence; dossiers, guarded reviews and canonical inventory implemented |
| 3 — background orchestration | SMARTS capture-to-worker handoff, bounded retained-artifact inbox and reviewed capture/worker timer bundle implemented; CEQA background network authorization and deployment remain partial |
| 4 — cooperating-source journey | Controlled arrival-order checks exist; complete realistic multi-source acceptance remains outstanding |
| 5 — native integration | Shared-state migration of native map, leads, dossiers, evidence, entity views and filters remains outstanding |
| 6 — live Relationship Graph | Durable backend events exist; live delivery, UI, replay and reconnection acceptance remain outstanding |
| 7 — assurance completion | Relevant new safeguards tested; complete historical-to-unified enforcement reconciliation remains outstanding |
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
- Access-basis gap: main accepts nonempty review text; PR #155 binds tri-state facts
  to immutable review/evidence digests. Unified enforcement remains to be reconciled.
- Native money uses Decimal/integer cents; older ledger models retain float fields.
  Complete financial/workflow equivalence remains unproven.
- Current SQLite connections enforce foreign keys; a historical test path is absent.
- Original operator UI remains preserved. Approved native design is unchanged by this
  backend continuation; absolute pixel parity is not claimed.

## Verification

- Earlier full regression before the last worker additions: **2,567 passed**, two
  upstream Typer/Click deprecation warnings, **663.78s**.
- Final-tree Python 3.12.14 full regression: **2,571 passed**, two upstream
  Typer/Click deprecation warnings, **595.59s**. This covers implementation `ff35100`;
  the subsequent checkpoint update changes only this status file.
- Focused foundation/source/site-resolution/database checks: 49 passed, two upstream
  warnings, 55.77s. Existing backup/schedule checks: five passed, 2.43s.
- Worker checks cover concurrency, dependencies, restart, stale leases, bounded retry,
  rollback, exact-byte tampering, bounded continuation, SMARTS cursor, backup/restore,
  concurrent enqueue during backup and CLI failure reporting. Both parcel-arrival
  orders passed separately (two cases, 6.72s).
- Ruff passed; strict Mypy passed for 341 modules; JavaScript syntax and pip check passed.
- Python 3.11, fresh browser/visual acceptance, vulnerability audit and complete final
  integration gates are not newly verified in this local continuation. No merge readiness claimed.

## Next immediately executable task

Finish Phase 3: connect existing authorized capture/CEQA producers and local scheduling
to this durable queue, respecting existing access reviews, rate limits and 403 stops.
Prove restart-safe source-to-investigation processing without an open UI or ChatGPT.
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
The current full regression is pending. Local Chromium is absent and its normal
Playwright download returned invalid/truncated archive data, so no local browser pass
is claimed. The existing GitHub visual workflow runs `tests/ui/schedule.js`, now checking
that both worker units are visible during review. The prior published checkpoint
`8b81ea9` passed GitHub CI and visual/browser workflows; those results do not cover this slice.

**PARTIAL / NEXT:** CEQA's current exact manual request allowances explicitly deny
background recurrence; no timer or inbox grants network permission or bypasses those
rules. Finish Phase 3 by implementing a separately scoped, reviewed CEQA background
acquisition capability using existing source checks, bounded plans, revocation and
durable effect allowances. Then prove the complete Phase 4 cooperating-source journey
before native-view migration, live graph and final assurance/parity acceptance.
