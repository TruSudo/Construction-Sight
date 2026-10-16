# ConstructionSight — active unification assignment

The controlling implementation assignment is the owner's **verbatim**
[master directive](docs/CONSTRUCTIONSIGHT_UNIFICATION_DIRECTIVE.txt).
Follow its Phase 1 → 8 implementation order and acceptance criteria. This checkpoint
adds no replacement doctrine. The approved native Command Center is the sole target
operator experience; all mandatory historical functionality and safeguards must survive.

**CURRENT: Phase 1 in progress. Phases 2–8 are not completed.**

Development branch: `agent/unification-preservation-audit-2026-10-16`.
Preserved remote baseline: `origin/main` at
`4c8f8eaf08653e2d571b0df821b862dcc9b158ac` (PR #231 integration).
Recovery commit: the latest commit on this development branch; obtain with `git rev-parse HEAD`.
No application code, data, source permissions, interfaces, branch history or commercial
authority changed in this checkpoint. No merge into main or branch deletion authorized.

## Phase 1 verified checkpoint — 2026-10-16

- Fetched origin into the retained repository; created an isolated clean development
  worktree from current main, leaving previous worktrees untouched.
- Enumerated 193 remote branch tips (excluding origin/HEAD): 110 are ancestors of
  main, 83 have commits absent from main. These counts include main and are ancestry
  evidence only; they do not establish lost functionality or equivalence.
- Full tip SHAs and divergence counts are retained in
  [baseline evidence](docs/audits/unification-preservation-baseline-2026-10-16.json).
- Explicitly located all three named archives: `archive/pre-pass-a-2026-10-15`
  (`7771e7d`), `archive/silent-risk-e47e335` (`e47e335`), and
  `archive/silent-risk-e49cca5` (`e49cca5`). All three tips are ancestors of main.
- `agent/silent-risk-certification` and `agent/native-assurance-remediation-076-096`
  are ancestors of main. `agent/native-assurance-remediation` has two commits absent
  from main. Preserve all; ancestry does not prove every safeguard remains enforced.

| Required PR | Verified remote state | Discovery disposition |
| --- | --- | --- |
| #143 | Open, unmerged | Source-inventory test-drive branch; functional reconciliation pending |
| #155 | Open, unmerged | Lawful-access fact authority; stronger immutable-basis contract differs from main |
| #158 | Open, unmerged | Frozen-candidate resolution map; not runtime integration proof |
| #186 | Open, unmerged | Operational confidence gating; equivalent behavior must be checked |
| #193 | Open, unmerged | Assurance evidence and remediation line; historical claims require exact-tree verification |
| #195 | Open, unmerged | Confidence test fixtures; regression reconciliation pending |
| #232 | Open, unmerged, draft | Pass B optimization; six commits ahead of baseline |
| #233 | Open, unmerged | Pass B-2 interface preservation; twelve commits ahead of baseline |

The preliminary `feature/unified-command-center-source-intelligence-2026-10-16`
branch is at `86bfc264a969e952a30ade987d6c510283a0af6d`, sixteen commits ahead of
baseline. Its read-only `source_intelligence_bridge.py` exposes government-record
views and candidates; it does not constitute the required shared investigation engine.
Its `_exact()` uses an incorrectly escaped whitespace expression. Executing that
function from the branch proves `123  Main St` and `123 Main St` compare unequal.
Do not promote this preliminary matcher to the unified identity service.

## Capability and safeguard findings — incomplete inventory

- Native `live_command_center.py` operates on SMARTS projections and local commercial
  state. Legacy `operator_web.py` exposes relational CEQA/permit, entity, evidence,
  source-registry and review routes. Common authoritative investigations have not
  been demonstrated. Both implementations remain intact.
- Existing `ArtifactResolutionService`, parcel/site resolution, `IntelligenceStore`,
  `IntelligenceGraphService` and neighborhood queries are reuse candidates. Focused
  tests demonstrate candidate safeguards, persisted evidence/reference validation,
  immutable evidence/event IDs and graph events in controlled fixtures. Connection
  of those safeguards to every native source path remains unproven.
- `collection_schedule.py` already generates persistent systemd user timers for daily
  capture. This is not proof of dependency-aware multi-source investigation jobs,
  durable task recovery, or automatic unified investigation publication.
- Current `legal.evaluate_access()` accepts `access_facts_reviewed=True` with a
  nonempty plain-text `review_basis` (`allowed`, reproduced offline). PR #155's
  branch instead requires tri-state restriction facts and an immutable review/evidence
  digest. This historical assurance difference needs call-path reconciliation;
  existing access-policy tests passing does not demonstrate that stronger contract.
- Historical `tests/test_database_integrity.py` is absent on main. Direct runtime
  inspection of a primary SQLite connection returns `PRAGMA foreign_keys=1`.
  Missing historical tests alone therefore do not prove that safeguard is absent.
- No live graph event-delivery, replay/reconnection, background retained-data journey,
  full cross-view agreement, or original-to-native parity acceptance demonstrated here.

**LIVE:** Existing controlled runtime HTTP, storage, identity and scheduling behaviors
exercise successfully in focused tests; no new feature deployed.

**INTEGRATED:** No new source integration claimed. Existing reusable services identified.

**ASSURANCE:** Preserved remote refs and exact assignment; checked current reference,
evidence/event immutability, identity, access and transaction-related regression suites.
Historical-to-native assurance equivalence remains incomplete.

**PARTIAL:** Phase 1 inventory and all downstream phases remain unfinished. Unique
branch code/test/evidence reconciliation, additional source families, retained-data
runtime demonstrations and the preliminary branch review remain pending.

**TESTS:** Python 3.12.14: first batch 161 passed in 21.22s (artifact identity/resolution,
parcel/site resolution, intelligence store, graph/neighborhood, collection schedule,
native HTTP and legacy dashboard); second batch 65 passed in 1.20s (access policy,
adapter, source verification, enrichment models/service, database, effect consumption,
result event integrity, derived identity integrity, parcel assurance). Total 226 passes,
20 test files, no failures in completed batches. An initial second-batch invocation
collected no tests because the historical database-integrity test path is absent;
corrected to current `tests/test_database.py`. Historical test behavior is still pending.
Python 3.11, full suite, browser/visual gates and complete integration checks not run
in this discovery checkpoint. No merge readiness claimed.

**NEXT:** Remain in Phase 1. Compare the 83 non-ancestor branches' unique runtime,
test and retained-evidence changes against main (starting with PR #155 access
contracts, native-assurance's two unique commits, #186/#195 confidence behavior,
and #193 evidence). Map each mandatory capability to an implementation, native
call path, regression evidence and explicit gap. Finish preliminary-branch review.
Only after this forensic inventory, proceed to Phase 2 using existing identity,
evidence and graph services; do not substitute aggregation for resolution.

---

## Prior checkpoint (historical; active checkpoint above supersedes planning claims)

# ConstructionSight

USGS map integration (development branch, CI pending): added opt-in official USGSImageryOnly, USGSImageryTopo, and USGSTopo cached basemaps through the existing layers control; retained offline provider, real-coordinate markers, dossier navigation, local map attribution, and all existing map tools. Corrected fractional-zoom image-to-marker scaling and capped USGS cache level at 16 (overzoom above that). Added map scale/geolocation coverage in operational mode, selectable basemap persistence, clear outage fallback, and a network-mocked browser regression. This is online historical geographic context, not evidence of current construction or site verification. Native mockup-parity mode hides the additional operational overlays. No main merge or owner-device deployment.\n\nPR #230 visual parity refinement (2026-10-15): original 1672×941 reference, calibration and imagery masks unchanged. Bundled Inter approximations, native decorative skyline with live tagline, texture fade, selected navigation geometry/icons, header, KPI numerals, dossier actions, and table/watch typography improve all eight regional peak scores versus main: sidebar 38.663 → 27.152; header 27.191 → 15.781; hero 73.842 → 34.995; KPIs 37.940 → 28.537; map 42.074 → 40.706; dossier 40.215 → 24.929; leads 24.648 → 23.125; watchlist 27.809 → 22.490. Ratchet retains measured improvements. Demo and retained genuine-data structure/fonts/baselines plus five viewport sizes pass; 33/33 actions, 33/33 complete contracts, 12/12 lead-to-royalty workflow checks, 2,522 Python tests (two upstream Typer/Click deprecation warnings), Ruff, strict Mypy (333 modules), JS syntax and dependency integrity pass locally. All eight fidelity thresholds still fail: absolute parity is not achieved. Raster-only reference supplies neither original font/vector specifications nor an identified satellite basemap source. Live controls/data remain functional; no screenshot substituted for geographic data. No owner-device deployment or main merge in this pass.

2026-10-15 operating-model revision proposed on development branch: active README policy adopts risk-based severity, one measurable outcome per complete vertical slice, focused development checks, unchanged blocking CI, explicit prototype/live/deployment states, and heightened reviews only for dangerous operations. Historical five-pass certification and universal zero-defect requirements are no longer proposed as ordinary merge gates. This changes process, not application behavior; PR/CI and owner-approved merge remain pending. No new sources implemented in this change.

PR #225 merged: main CI is green. Installed-app tests, Ruff, strict Mypy, JavaScript and vulnerabilities block merges; 98 superseded narratives are archived without changing evidence.

PR #226 merged: unknown types 804/1,563 (51.44%) → 542 (34.68%); non-excluded unknowns 38.44%, so the earlier under-30% goal remains unmet. All new parcel-use claims are unverified. The ranked company export covers 809 companies/1,097 sites; 402 shared-contact and 57 consultant flags remain visible. The explicit evidence-review queue works; real leads still require operator verification.

Native visual: original 1672×941 reference retained byte-for-byte; SHA-256 00a043ec464728b2275ba3372421b89e1e31d7a7a76dcdb20ced9628bea03f3f. Native boxes, estimated baselines, bundled fonts and 13 calibration challenges pass. Pixel fidelity remains below calibrated thresholds in all eight regions; original font identity is unknown, with icon/texture differences also reported. Pixel scores remain a non-blocking ratchet.

Cleanup pending authenticated browser access: original 103 merged names include main; skip main and 23 branches with open PRs, leaving 79 eligible originals. The separate 79 unmerged branches are untouched. Remote tag publication and auto-delete remain pending; no branches have been deleted.
