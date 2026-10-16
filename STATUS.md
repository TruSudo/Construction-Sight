# ConstructionSight — system unification

**Controlling assignment:** the owner's [verbatim master directive](docs/CONSTRUCTIONSIGHT_UNIFICATION_DIRECTIVE.txt).
Follow Phases 1–8 and their acceptance criteria. One shared intelligence engine,
one investigation state, the approved native Command Center, and the live Relationship
Graph remain the target. Preserve all mandatory historical functionality and safeguards.

**CURRENT:** preservation inventory established; Phase 2 investigation foundation in
progress. Phases 3–8 are not accepted or complete. Full historical/native equivalence
is unproven and remains an explicit acceptance obligation.

Development branch: `agent/unification-implementation-2026-10-16`, based on preserved
checkpoint `eef0aca71ea61b19aff43d7ccfb056640454170b` and main baseline
`4c8f8eaf08653e2d571b0df821b862dcc9b158ac`. Recovery SHA is the latest commit
on this branch (`git rev-parse HEAD`). No main merge, branch deletion, history rewrite,
original-UI retirement, source-authority expansion or owner-device deployment performed.

## Preservation/capability findings

[Machine-readable evidence](docs/audits/unification-preservation-baseline-2026-10-16.json)
retains all 193 baseline remote tips; 110 are ancestors of main and 83 have unique
commits. It now also catalogs each non-ancestor branch's contributed runtime/test/
evidence paths, all 333 baseline Python modules, direct test imports, static native/
legacy import reachability, and the ten existing declared capability families.
File ancestry/import reachability never substitutes for functional proof.

Explicit archive verification: `archive/pre-pass-a-2026-10-15` at `7771e7d`,
`archive/silent-risk-e47e335` at `e47e335`, and `archive/silent-risk-e49cca5`
at `e49cca5` are retained ancestors of main. Native-assurance branch `10037faa`
and silent-risk certification are ancestors; native-assurance `3e11e27` retains two
unique commits. No historical assets discarded.

Required PRs #143/#155/#158/#186/#193/#195/#232/#233 were checked: all are open
and unmerged. #232 and #233 retain six and twelve commits beyond main respectively.
The preliminary unified branch `86bfc264` has sixteen commits beyond main; it is a
read-only aggregation/candidate view, not the required engine. Its incorrectly escaped
whitespace comparator fails a repeated-space equality check; that matcher was not adopted.

| Capability family | Current disposition and integration obligation |
| --- | --- |
| SMARTS intake, retained bytes, aliases, revisions | Implemented; bounded validated offline replay now reaches existing intelligence persistence |
| CEQA listing/detail/CSV, recurring manifests, write plans, inbox | Implemented in historical/operator paths; typed retained CEQA records now reach common persistence; automatic acquisition still pending |
| Permit, planning, agendas, lifecycle observations | Existing domain/adapters retained; typed permits now reach common persistence; remaining producers pending |
| Parcel/ArcGIS acquisition, containment, assurance, longitudinal state | Existing services retained; parcel-core evidence normalization available; automatic parcel/site enrichment pending |
| Entity/contractor/contact records | Existing services retained; CEQA/permit source parties enter common graph as unverified source claims; canonical cross-source entity resolution pending |
| Artifact identity and parcel-backed site resolution | Existing resolver reused for project candidates; SMARTS location projection reuses existing intake/site resolver; no automatic identity merge |
| Intelligence evidence, relationships, clusters and revision history | Existing store/graph reused; no additional database schema or competing matching engine |
| Native map, leads, dossiers, evidence, filters, entity views | Existing native behavior retained; shared-state replacement/integration is still pending Phase 5 |
| Background work, watchlists and alerts | Existing capture timer/watchlists retained; durable coordinated multi-source jobs and reassessment are missing |
| Live Relationship Graph and history | Existing graph/query/event backend retained; live delivery, replay, reconnection and graph UI missing |
| Outreach, bids, catalog and royalty/result ledgers | Both implementations retained; full equivalent functionality not established; no automated sending or binding action |
| Assurance, recovery, supply-chain and dependency integrity | Existing assets preserved; cross-runtime enforcement must be demonstrated in Phase 7 |

Eight historical production paths are absent from main: three old CSV export modules,
`money.py`, three old result-ledger-authority modules, and the preliminary source bridge.
The evidence records current counterparts and exact gaps. Five historical test paths,
one patch script, 25 assurance evidence paths and one closure proof also remain branch-
retained. No absent filename is treated as proof that its behavior was lost or replaced.

Known assurance differences: main's reviewed access basis accepts nonempty free text;
PR #155 binds tri-state facts to immutable review/evidence digests. Native money uses
Decimal/integer cents while older ledger models retain float fields; exact historical
parity is unproven. Current SQLite connections enforce foreign keys; a historical test
file is missing. These remain explicit remediation/verification obligations.

## First investigation foundation slice

- `InvestigationService` composes existing `IntelligenceStore`, `IntelligenceGraphService`,
  `ArtifactResolutionService`, source schemas and revision history. Source IDs remain
  separate; same parcel/address produces a review candidate, never verified project identity.
- Source observations bind normalization to immutable receipts and retained evidence.
  Replays are idempotent, out-of-order records retain history without regressing current
  source facts, conflicting artifacts remain explicit, and obsolete candidates become stale.
- CEQA/permit participant roles enter the graph as source claims; reviewed party relationships
  are preserved for review. Correlation cannot reopen a reviewed/superseded decision.
- SQLite savepoints are anchored to the caller's outer transaction. Failure injection proves
  rollback after evidence writes and after the entire ingestion operation.
- Existing graph service suppresses unchanged replay events; generic entity updates no longer
  falsely emit ENTITY_MERGED. Historical ENTITY_MERGED events remain readable.
- New offline entrypoint: `constructionsight-investigations` or
  `python -m constructionsight.investigation_cli --database PRIVATE_DIR/investigations.sqlite3
  --source SOURCE --kind smarts-journal|ceqa|permit|parcel --limit 100`.
  SMARTS `--after-id` resumes a bounded read. Source access is read-only and destination
  files require private ownership/modes. No network is performed.

**LIVE:** Actual retained SMARTS replay: ten observations -> ten investigations,
ten source nodes, ten evidence records, ninety committed events. Replay produces
exactly the same counts. Two genuine retained CEQA records enter the same store.
The original 1.6 GB journal SHA-256 remains
`0f64415f983c136bdb7621ae52b1977b269ae9ea2e15b3c4f36f7a17b80d000f`.
No cross-source match or current construction claim is inferred from this demonstration.

**INTEGRATED:** Bounded offline source replay reaches existing shared persistence,
identity candidate analysis, participants and retained graph/revision events. Native
views and autonomous source cooperation are not connected yet.

**ASSURANCE:** Evidence/normalization rebinding rejection, duplicate suppression,
source identity/alias checks, caller rollback, failure recovery, county scoping,
contradiction retention, candidate invalidation and preservation of reviewed decisions
are implemented with focused checks. Wider assurance parity remains pending.

**PARTIAL:** Phase 2 lacks completed shared dossier/query projections, full existing
producer integration, reviewed cross-source investigation membership and parcel-backed
corroboration. No durable coordinated jobs, live graph UI, native migration or final
functional parity acceptance claimed. Phases 3–8 remain outstanding.

**TESTS:** Baseline Python 3.12.14: 2,522 passed, two upstream Typer/Click warnings,
97.51s. Focused foundation/source/graph/journal set: 29 passed in 2.56s before the
latest candidate-invalidation tests and event-label corrections. Latest full suite: 2,538 passed, two upstream warnings, 106.67s. Ruff passes;
strict Mypy passes across 336 source modules. JavaScript syntax passes across all
source/test JS files. Python 3.11, complete browser/visual and final integration
acceptance remain pending; no merge readiness claimed.
Initial implementation failures were corrected, including empty cluster validation,
false replay activity, regenerated preview timestamps and computed provenance fields
breaking strict round-trip validation. Genuine retained-data replay is rerun successfully.

**NEXT:** Finish and verify this Phase 2 slice, publish a recoverable development
commit, then add common investigation query/dossier projections and connect remaining
existing producers. Finish Phase 2 acceptance before moving to durable background jobs
(Phase 3), cross-source journey (Phase 4), native view integration (Phase 5), live graph
(Phase 6), assurance completion (Phase 7) and full functional parity (Phase 8).
