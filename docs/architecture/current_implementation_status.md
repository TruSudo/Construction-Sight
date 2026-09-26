# Current Implementation Status

This document reconciles implemented ConstructionSight layers with documentation, persistence, CLI exposure, live-source status, certification controls, and known limitations.

## Status labels

- `implemented`: model/service logic exists in `src/constructionsight`.
- `tested`: dedicated tests exist in `tests`.
- `documented`: architecture documentation exists.
- `persisted`: SQLAlchemy ORM/store coverage exists.
- `cli`: an operator-facing command exists.
- `live_source_integrated`: lawful live execution is implemented and represented as live.
- `planned`: identified product scope that is intentionally not implemented.

A planned capability is not an active defect when the current supported boundary is explicit, guarded, tested, and non-overclaiming.

## Pipeline status

| Layer | Implemented | Tested | Documented | Persisted | CLI | Live source integrated | Status note |
|---|---:|---:|---:|---:|---:|---:|---|
| Lawful intake boundary | Yes | Yes | Yes | Partial | Yes | No | Public-access boundaries are documented and tested through intake and adapter contracts. |
| Source registry | Yes | Yes | Yes | Yes | Yes | No | CEQAnet is evidence-backed `partial`; the other three canonical sources remain unverified. Partial status does not establish verified usable coverage. |
| Source readiness workflow | Yes | Yes | Yes | No | Yes | No | Report-only readiness preserves source identity, lawful boundary, adapter/source state, reachability, reasons, limitations, and next action. |
| Source audit package | Yes | Yes | Yes | No | Yes | No | Report-only audit packages preserve URL, HTTP, redirect, maturity, reason, limitation, and next-action evidence. |
| Source verification checklist | Yes | Yes | Yes | File-backed | Yes | No | Browser-reviewed CEQAnet evidence, policy review, automated-access failure, and remaining limitations are preserved without authorizing recurring collection. |
| Source plan reports | Yes | Yes | Yes | No | Yes | No | Dry-run plans preserve proposed payloads, evidence, complete-registry digests, and deterministic approval digests. |
| Source registry controlled apply | Yes | Yes | Yes | File-backed | Yes | No | Explicit apply validates complete snapshots, digests, evidence, counts, identity, status-only mutation, path separation, audit output, and target-last replacement. |
| Adapter contracts | Yes | Yes | Yes | N/A | Yes | No | Contracts are not represented as verified live integrations. |
| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact planning, one-request proof execution, strict UTF-8-first/Windows-1252 decoding, and offline replay verification are implemented. The retained HTTP 200 body replays successfully with 2 rows. No persistence, scheduling, or source promotion is claimed. |
| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact-schema definitions, manifests, executions, and verifications bind source evidence, exact windows, attempts, retained response envelopes, and current-evidence authority. Canonical CEQAnet maturity is `partial`, so the verified-only execution gate remains closed. |
| CEQAnet maturity proposal | Yes | Yes | Yes | Artifact-only | Yes | No | Offline proposal and independent verification bind the registry, live execution, body, replay, and inspection digests. The only supported decision is `keep_partial`; mutation and recurring authority are fixed false. |
| CEQAnet CSV access policy | Yes | Yes | Yes | Artifact-only | Yes | Evidence only | A verified, expiring policy permits one explicit official-CSV GET per UTC day with zero retries and mandatory retention/verification. Production recurring execution and promotion remain false. |
| CEQAnet CSV evidence series | Yes | Yes | Yes | Artifact-only | Yes | Governed evidence only | Policy-bound execution envelopes and immutable digest-chained snapshots enforce one execution per UTC day, complete evidence/verification bindings, terminal access-control halts, and report-only readiness. Sequence 1 contains one successful project observation from UTC 2026-07-14; three later observations including document scope remain. |
| Universal intake | Yes | Yes | Yes | Partial | Yes | No | Source-neutral records and routing exist; live source breadth is intentionally limited. |
| Opportunity transition intake | Yes | Yes | Yes | Partial | Yes | No | Converts universal intake facts into opportunity candidates without implying outreach. Draft operator source-candidate previews are a distinct, read-only bridge from retained normalized CEQA/permit records; no fabricated universal intake, commercial scoring, candidate persistence or automatic conversion is authorized. |
| Exact-source candidate review docket | Draft only | Synthetic SQLite/CLI regression | Yes | Append-only normalized source reviews | Explicit local CLI | No | Separately staged, unapproved content-bound CEQA/permit source snapshots require an exact expected preview/source digest, recorded actor/rationale, scoped confirmation, effect reservation, atomic source revalidation, and integrity-checked readback. The GUI remains GET-only; no commercial lead, score, approval, outreach or bid is produced. This is not merged into main or operationally certified. |
| Shovels/Regrid gap alignment | Yes | Yes | Yes | N/A | Yes | No | Capability planning exists; it is not a parity claim. |
| Parcel/site resolution | Yes | Yes | Yes | Yes | Yes | No | Hint and parcel-backed resolution preserve confidence, ambiguity, limitations, storage, topology, and read-only inspection. |
| Parcel source registry | Yes | Yes | Yes | Config | Yes | No | Official San Bernardino and Riverside endpoints and exact preview mappings are registered; county/state scope constants remain distinct from physical fields. |
| Parcel source verification | Yes | Yes | Yes | Yes | Yes | No | Eight digest-bound official observations support two immutable preview profiles, field-specific assurance contexts, and explicit county coverage gaps. No full acquisition or countywide completeness is claimed. |
| Parcel ArcGIS acquisition gates | Yes | Yes | Yes | Yes | Yes | Bounded on demand | Exact capability snapshots, retained bounded proofs, a complete-rehearsal executor, official HTTP adapter, and portable independently verifiable proof bundle exist. An exact-plan, maximum-24-hour, single-use authorization and offline preflight now guard eligibility for one future live rehearsal while fixing credential, bypass, import, promotion, recurring, and production-bulk authority false. A ConstructionSight-owned durable SQLite consumption ledger exists; its complete effect-boundary integration remains under CS-SR-061 review. No completed live county rehearsal is claimed. |
| Parcel schema preview | Yes | Yes | Yes | No | Yes | No | Pre-import schema gate exists. |
| Parcel row preview | Yes | Yes | Yes | No | Yes | No | Pre-record row gate exists. |
| Parcel core record | Yes | Yes | Yes | Yes | Yes | No | Raw geometry, hashes, CRS labels, compatible summaries, persistence, and read-only inspection exist. |
| Parcel longitudinal evidence | Yes | Yes | Yes | Yes | Yes | No | Complete digest-bound observations remain append-only; source-effective/observed-time selection records explicit supersession and blocks ambiguous timelines. |
| Parcel fact assurance | Yes | Yes | Yes | Yes | Yes | No | Caller-governed or longitudinally selected current records produce field-level claims and explainable authority, lineage, agreement, conflict, and missing-evidence outcomes without a global truth score. |
| Geometry normalization and topology | Yes | Yes | Yes | Payload | Partial | No | GeoJSON and WKT/EWKT topology, holes, parts, extra dimensions, embedded SRIDs, source-plane area centroids, and conservative CRS refusal exist. |
| Parcel-backed site resolution | Yes | Yes | Yes | Yes | Yes | No | Point and topology matches are distinguished from explicit limited fallback; incompatible CRS is never directly compared to longitude/latitude. |
| Permit snapshot transition spine | Yes | Yes | Yes | Yes | Yes | No | Persisted snapshots and transitions have read-only list/detail access. |
| Contractor identity | Yes | Yes | Yes | Yes | Yes | No | Persisted identities have read-only list/detail access. |
| Decision record | Yes | Yes | Yes | Yes | Yes | No | Persisted decisions have read-only list/detail access. |
| Opportunity enrichment | Yes | Yes | Yes | Yes | Yes | No | Versioned scoring reports are persisted and operator-visible. |
| Lead review package | Yes | Yes | Yes | Yes | Yes | No | Full review payloads, reasons, limitations, and scores remain visible. |
| Lead dedupe | Yes | Yes | Yes | Yes | Yes | No | Fingerprints and duplicate results are persisted and visible. |
| Lead workflow status | Yes | Yes | Yes | Yes | Yes | No | Matrix-valid, exact-state transitions preserve append-only unique events. |
| Result ledger/share authority | Yes | Yes | Yes | Yes | Yes | No | Immutable revisions, serialized exact-state authority heads, and append-only operator events govern result entry and correction. |
| Repository certification | Yes | Yes | Yes | N/A | Yes | N/A | Every tracked file is scanned; CI enforces dependency integrity, strict lint/type/test gates, warning failure, clean worktree, and diff hygiene. |
| Outreach preview | No | No | No | No | No | No | Planned product capability; no external action is implied. |
| UI/operator app | Partial (draft) | Partial (synthetic) | Yes | Read-only existing tables | Yes | No | Draft PR #119 serves a loopback-only GUI over retained CEQA/permit records and exact lead reviews. It provides bounded source-claimed map points, exact stored-key entity co-occurrence, and recorded source-event dates. No real-browser acceptance, verified current construction stage, production collection, outreach, bids, or release authority exists. |

## Active defect ledger

A certified tree must contain zero active defects. Any new runtime, data-quality, documentation, persistence, provenance, compatibility, security, or CI defect is recorded here immediately and blocks feature work until resolved.

Current active-defect count: **21**. The authoritative ledger is `governance/active_defects.toml`; on this remediation line it contains `CS-SR-076` through `CS-SR-096`, all discovered against frozen assurance commit `539939a8cdef813b919b1c725fa1439d03d97ea7`. The prior CS-SR-001 through CS-SR-075 series is historical resolved-defect evidence and must not be represented as current active state.

The first September 21 correction batch pins every component when reading CEQAnet bundle evidence and ArcGIS proof files, fails closed without atomic no-follow support, binds ZIP verification to immutable bounded input bytes, and bounds ZIP directory allocation before parsing. A second batch applies pinned private staging, bounded create-only publication and verified durable replay to retained ArcGIS responses, checkpoints and portable proofs. A third batch applies the bounded no-follow reader to operator JSON/HTML, CSV and universal intake, and binds HTML detection and extraction to one byte snapshot. A fourth batch routes 33 CLI output modules and CEQAnet bundle/ZIP publication through pinned, bounded atomic publication, preserves create-only conflicts, and uses one anonymous ZIP staging handle. Coupled registry/bundle commits, success-record ordering, deterministic recovery and full path/platform qualification remain open work under CS-SR-054/055/058/061. Unsupported filesystem platforms reject these evidence reads; successful native Windows operation has not been established.

Individual defect closure requires its stated correction and retained regression/evidence criteria. Final release certification additionally requires a new frozen exact tree, five authentic context-isolated Native Maximum Assurance passes under ADR-0009 with complete coverage, zero active defects, all exact-environment quality gates, and authenticated owner acceptance. No release or merge readiness is claimed. Remediation PR #197 and CI-only PR #198 remain drafts.

## Resolved defect ledger

These are historical remediation records. The active CS-SR ledger above governs current defects and supersedes any broader completion claim in a historical entry; these records do not establish current release assurance.

| ID | Severity | Layer | Resolved defect | Resolution |
|---|---|---|---|---|
| CS-VIAM-001 | P1 | Doctrine | README and runtime status drifted. | README, architecture status, and audit inventory are reconciled and certification checks forward drift. |
| CS-VIAM-002 | P1 | Persistence | Core movement, identity, parcel, site, and post-enrichment records lacked dedicated storage. | Dedicated ORM/store coverage preserves indexed fields and complete payloads. |
| CS-VIAM-003 | P1 | Source maturity | Seed records, reachability, adapter contracts, and verified usable sources could be conflated. | Layered status, readiness, audit, checklist, planning, digest, and controlled-apply governance separates each maturity class. |
| CS-VIAM-004 | P1 | Adapter maturity claims | Placeholder contracts could be mistaken for live integrations. | Source-status reporting and documentation explicitly prevent live-coverage claims. |
| CS-VIAM-005 | P1 | Geometry | Envelope-only matching, coordinate-average centroids, unparsed WKT, and direct cross-CRS comparisons could produce false spatial conclusions. | Supported GeoJSON/WKT topology, area-weighted source-plane centroids, CRS conflict preservation, and incompatible-CRS refusal are implemented and tested. |
| CS-VIAM-006 | P1 | Scoring | Scoring constants lacked profile identity. | Versioned scoring profiles are persisted with reports. |
| CS-VIAM-007 | P1 | Workflow | Workflow status changes lacked a complete transition matrix. | Matrix enforcement and final-state immutability are implemented. |
| CS-VIAM-008 | P1 | Result ledger | Share uncertainty was represented only in prose. | Explicit share states are modeled and persisted. |
| CS-VIAM-009 | P2 | Operator access | Persisted records lacked consolidated inspection and governed actions. | Upstream read-only, lead, workflow, and result-authority commands expose the supported operator surface. |
| CS-VIAM-010 | P2 | Documentation | Architecture documentation lagged runtime. | Architecture, status, README, and audit ledgers are synchronized. |
| CS-VIAM-011 | P1 | Workflow event identity | Repeated transition cycles could reuse an event ID and overwrite history. | Event sequence participates in identity; duplicate IDs are rejected and repeated cycles are tested. |
| CS-VIAM-012 | P1 | Result authority | Differing outcomes lacked complete immutable correction and concurrency governance. | Linear immutable revisions, exact-state authority heads, and append-only authority events are enforced. |
| CS-VIAM-013 | P1 | Upstream mutation boundary | Generic edits could bypass source-specific provenance and domain builders. | Generic mutation is unavailable; only read access exists until a domain-specific governed action is justified. |
| CS-VIAM-014 | P1 | Certification governance | CI success did not independently scan every tracked file or distinguish planned scope from active defects. | `constructionsight-certify` and permanent CI certification gates now enforce the complete tracked-tree and governance boundary. |
| CS-VIAM-015 | P1 | CEQAnet query truth | `text_terms` counted as a bounding filter even though the verified CEQAnet request contract did not transmit it. | Listing and recurring-run query models reject free-text terms, so no run can claim an unapplied filter. |
| CS-VIAM-016 | P1 | CEQAnet execution evidence | Initial recurring-run executions had semantic verification but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest now bind bodies, URLs, counts, queries, flags, identities, and the no-persistence assertion before semantic verification. |
| CS-VIAM-017 | P1 | Evidence phase integrity | PR #93 merged temporary collection tooling while the intended evidence artifacts were absent. | The evidence packet and audit are committed, canonical CI is restored, temporary tooling is removed, and final tree contents are explicitly verified. |
| CS-VIAM-018 | P1 | Source access truth | Brittle page-marker and robots assumptions could misclassify valid pages or imply an access conclusion; later automated access returned HTTP 403. | Official page structures and policies were reviewed, the 403 and robots uncertainty are preserved, no bypass was attempted, and maturity is limited to `partial`. |
| CS-VIAM-019 | P1 | CEQAnet CSV encoding | The first live CSV proof returned HTTP 200 but the UTF-8-only parser rejected a source Windows-1252 byte. | Parsing now prefers strict UTF-8 and falls back explicitly to Windows-1252; the exact retained body is replayed offline, digest-bound, independently verified, and tested without another request. |
| CS-VIAM-020 | P1 | Replay phase final-tree integrity | PR #100 merged two write-enabled self-patching workflows and two patch scripts after the replay runtime landed, leaving CI coupled to a stale feature branch. | PR #101 removes all four temporary files, expands the committed absence assertion, restores canonical CI-only validation, and certifies the final production tree. |
| CS-VIAM-021 | P1 | Live evidence proxy transport | The governed executor honored environment SOCKS proxies while the package declared plain `httpx`, so a SOCKS-configured execution environment could fail before client construction and evidence retention. | The runtime dependency now declares `httpx[socks]`; certification imports `socksio`, and the first governed request succeeded with a complete verified artifact after the transport was present. |
| CS-VIAM-022 | P1 | ArcGIS bulk rehearsal evidence | Complete-rehearsal maturity could be asserted from bare checkpoint/retry booleans and opaque page digests without a retained proof chain. | Manifests now embed structured digest-bound page, checkpoint, resume, and retry evidence; all summary counts, flags, and digests are recomputed and disagreement is rejected. |
| CS-VIAM-023 | P1 | ArcGIS complete-rehearsal response evidence | A reusable rehearsal executor could otherwise derive page digests from parsed mappings without retaining the exact successful starting-count, page, and ending-count response bodies needed for independent proof. | Count and page sources now return exact response-byte envelopes; an atomic digest-addressed artifact store retains every successful body, receipts are contiguous, and page receipt digests must equal the manifest page digests. |

## Planned capability ledger

These entries are future product scope, not defects in the current supported implementation.

| ID | Capability | Current safe boundary | Required entry condition |
|---|---|---|---|
| CS-PLAN-001 | Optional preview archives and nested child tables | Current core records are losslessly persisted; report/config layers remain deliberately ephemeral. | Add only when replay or query requirements justify schema expansion. |
| CS-PLAN-002 | Verified recurring live adapters | CEQAnet remains `partial`; the digest-bound policy and sequence-1 evidence-series head govern explicit one-request, zero-retry official-CSV observations through 2026-08-13. One project observation passed on UTC 2026-07-14. HTML automation, production scheduling, domain persistence, and promotion remain unauthorized. | Collect and independently verify three additional successful observations on later unused UTC dates, including document scope, before another maturity review. |
| CS-PLAN-003 | CRS transformation, projection-aware/geodesic calculations, and topology repair | Incompatible CRS is preserved and refused rather than guessed; current results are not survey-grade. | Select and pin a GIS stack, define provenance and failure doctrine, and add exact tests. |
| CS-PLAN-004 | Domain-specific upstream corrections | Generic upstream mutation is blocked. | Define source-aware stale-state, correction, supersession, and audit semantics per record family. |
| CS-PLAN-005 | Workflow reopen or override | Final states remain immutable. | Introduce explicit authority, reason, stale-state, and append-only event doctrine. |
| CS-PLAN-006 | Outreach preview and sending | No external sending behavior exists. | Implement preview, approval, dedupe, compliance, evidence, and delivery audit boundaries first. |
| CS-PLAN-007 | Complete GUI/operator application | CLI/persisted services remain the supported operator surface; draft PR #119 contains a separate, read-only local development GUI. | Validate the GUI against populated local evidence in a real browser, connect governed source-to-opportunity persistence, implement safe operator actions and historical relationship views, and obtain exact-head CI plus required Native Maximum Assurance before any operational release. |
| CS-PLAN-008 | Countywide parcel evidence ingestion | Exact metadata, retained bounded proofs, an exact-response executor, official HTTP adapter, portable proof bundle, and an exact-plan expiring single-use authorization/preflight contract exist. Both sources remain `bounded_query_verified`; no completed live county rehearsal is claimed and consumption integration remains under CS-SR-061 review. | Complete and verify authorization-consumption integration; separately issue and consume one authorization per county; execute, save, and independently verify each portable rehearsal bundle; then review profile promotion and recurring observation orchestration as distinct later phases. |

## Forward cleanup rule

Every future feature PR must update this matrix or explicitly state why no status changed. New models and services must not bypass tests, documentation, persistence review, CLI review, lawful-access review, limitation/provenance review, compatibility review, or repository certification.

See [the canonical full-repo audit inventory](../audits/full_repo_audit_inventory.md).
