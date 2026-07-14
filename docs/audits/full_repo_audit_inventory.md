# Full-Repo Audit Inventory

This document is the canonical repository-wide inventory for ConstructionSight. It distinguishes implemented runtime, resolved defects, planned capabilities, live-source maturity, persistence truth, operator exposure, and certification requirements.

See [the repository certification protocol](repository_certification.md) and [the current implementation-status matrix](../architecture/current_implementation_status.md).

## Executive status

ConstructionSight has a substantial tested model/service architecture for lawful public-record construction intelligence. Implemented strengths include:

- source-neutral intake and guarded CEQAnet tooling;
- layered source status, readiness, audit, checklist, planning, and controlled apply governance;
- exact-schema CEQAnet recurring-run definitions, exact-window manifests, digest-bound attempts, stale-evidence checks, and execution verification;
- browser-reviewed CEQAnet source evidence with an explicit partial-maturity and automated-access boundary;
- a source-provided CEQAnet CSV URL/body contract with offline inspection and a one-request/no-retry live-proof envelope;
- digest-bound, report-only CEQAnet maturity proposals that cannot promote or authorize recurring execution;
- an offline, digest-bound, 31-day-maximum CEQAnet official-CSV access policy with explicit per-execution authorization, daily request limits, complete-body retention, independent verification, and no production authority;
- policy-bound CEQAnet evidence executions and immutable series snapshots with exact artifact references, independent recomputation, daily uniqueness, terminal access-control halts, and report-only maturity readiness;
- parcel and site reasoning with GeoJSON and WKT/EWKT topology;
- source-plane area-weighted polygon centroids and conservative CRS boundaries;
- permit movement, contractor identity, and decision records;
- versioned opportunity enrichment, lead review, and dedupe;
- matrix-constrained lead workflow status;
- immutable result revisions, explicit share state, serialized authority, and audit events;
- dedicated persistence for core upstream and post-enrichment records;
- read-only upstream inspection and governed lead/result actions; and
- an executable complete tracked-tree certification gate.

ConstructionSight is not yet a production recurring live-source platform. Most adapter families are contracts or planned integrations. CEQAnet is canonically `partial`: HTML automation returned HTTP 403 without bypass, while the source-provided CSV endpoint has returned two retained HTTP 200 responses. The original UTF-8 failure remains preserved, and an offline Windows-1252 replay of that exact body passes with 2 rows. Sequence 1 adds one separately authorized, zero-retry project observation whose complete Windows-1252 body also verifies with 2 rows. The other three canonical sources remain unverified. A bounded official-CSV policy and digest-chained series ledger govern the evidence, but neither promotes the source nor authorizes production. No source is currently `verified`, no production scheduler exists, and no external outreach-sending behavior or GUI/operator application is implemented.

## Certification status model

Certification is evaluated for an exact Git tree. A certifiable tree must pass the complete Python 3.11 and 3.12 matrix, all domain audits, the tracked-tree certification command, warning failure, clean-worktree verification, and diff hygiene.

The active-defect count for a certified tree must be zero. Planned capabilities and external-source access limitations are not counted as software defects when their boundaries are explicit, guarded, non-overclaiming, and recorded with entry conditions.

## Pipeline inventory

| Layer | Implemented | Tested | Documented | Persisted | Operator access | Live source integrated | Current boundary |
|---|---:|---:|---:|---:|---:|---:|---|
| Lawful intake boundary | Yes | Yes | Yes | Partial | Yes | No | Public-access constraints and unknown fields remain explicit. |
| Source registry | Yes | Yes | Yes | File-backed | Yes | No | CEQAnet is `partial`; three sources remain unverified; verified usable coverage remains zero. |
| Source readiness/audit/checklist/plans | Yes | Yes | Yes | Report/file-backed | Yes | No | Evidence and proposed actions do not silently authorize live collection. |
| Controlled source registry apply | Yes | Yes | Yes | File-backed | Yes | No | Full-snapshot, digest, evidence, identity, status-only, path, audit, and explicit-authorization controls apply. |
| Adapter contracts | Yes | Yes | Yes | N/A | Yes | No | Contracts are not live-integration claims. |
| CEQAnet guarded tooling | Yes | Yes | Yes | Partial | Yes | Guarded only | Bounded execution, offline parsing, persistence planning/application, export, and archive verification exist, but the canonical source is not execution-authorized. |
| CEQAnet official CSV contract | Yes | Yes | Yes | Artifact-only | Yes | Guarded proof only | Exact planning, one no-retry GET, strict UTF-8-first/Windows-1252 parsing, and offline replay are canonical. The retained HTTP 200 body replays successfully with 2 rows; no persistence is claimed. |
| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact schemas and canonical digests bind source identity, evidence, query, window, attempts, and retained response envelopes. `partial` maturity fails the verified-only execution gate. |
| CEQAnet maturity proposal | Yes | Yes | Yes | Artifact-only | Yes | No | Exact registry/execution/body/replay/inspection bindings produce only `keep_partial`; network, persistence, mutation, and recurring authority remain false. |
| CEQAnet CSV access policy | Yes | Yes | Yes | Artifact-only | Yes | No | The policy is effective 2026-07-14 through 2026-08-13, requires explicit authorization for each evidence execution, and permits at most one official `/Search` CSV GET per UTC day with zero retries. It does not itself perform a request or authorize production use. |
| CEQAnet CSV evidence series | Yes | Yes | Yes | Artifact-only | Yes | Governed evidence only | Complete policy-bound execution artifacts and compact immutable observations enforce full-chain verification, one execution per UTC day, exact response/body identity, and terminal access-control halts. Sequence 1 contains one verified project observation from UTC 2026-07-14 and remains `collecting`. |
| CEQAnet source evidence | Yes | N/A | Yes | File-backed | Yes | No | Browser review preserves official entry/search/detail/policy/CSV surfaces, workflow diagnostics, HTTP 403, robots uncertainty, and no-bypass limitations. |
| Universal intake | Yes | Yes | Yes | Partial | Yes | No | Source breadth remains limited. |
| Opportunity transition intake | Yes | Yes | Yes | Partial | Yes | No | Candidate production is not outreach. |
| External intelligence/gap spine | Yes | Yes | Yes | N/A | Yes | No | Capability models do not establish vendor parity. |
| Parcel source/schema/row preview | Yes | Yes | Yes | Config/report-backed | Yes | No | Live import remains absent. |
| Parcel core records | Yes | Yes | Yes | Yes | Read-only | No | Raw geometry, hash, CRS, and compatible summaries are preserved. |
| Geometry normalization/topology | Yes | Yes | Yes | Payload | Internal | No | Supported GeoJSON/WKT topology and conservative CRS refusal exist; no survey-grade claim is made. |
| Parcel-backed site resolution | Yes | Yes | Yes | Yes | Read-only | No | Exact point/topology signals are separated from explicit limited fallback. |
| Permit snapshots/transitions | Yes | Yes | Yes | Yes | Read-only | No | Recurring live polling is planned capability. |
| Contractor identities | Yes | Yes | Yes | Yes | Read-only | No | Live CSLB verification and governed correction are planned capability. |
| Decision records | Yes | Yes | Yes | Yes | Read-only | No | Agenda/staff-report live adapters are planned capability. |
| Opportunity enrichment | Yes | Yes | Yes | Yes | Yes | No | Score profile identity and full evidence are preserved. |
| Lead review/dedupe | Yes | Yes | Yes | Yes | Yes | No | Review and duplicate evidence remain inspectable. |
| Lead workflow status | Yes | Yes | Yes | Yes | Yes | No | Exact-state matrix-valid transitions append unique events. |
| Result ledger/share authority | Yes | Yes | Yes | Yes | Yes | No | Immutable revisions and serialized exact-state authority govern corrections. |
| Repository certification | Yes | Yes | Yes | N/A | Yes | N/A | Complete tracked-tree and CI policy validation is permanent. |
| Outreach preview/sending | No | No | Planned | No | No | No | No external action is implied. |
| GUI/operator application | No | No | Planned | No | No | No | CLI remains the supported interface. |

## Active defect ledger

**No active defect may be present in a certified tree.**

Any newly discovered defect is added here immediately, invalidates certification, and blocks feature work until the entry is resolved and moved to the resolved-defect ledger. The certification PR itself remains incomplete while this ledger is nonempty or any executable audit finding remains.

Current active entries: **none recorded in the canonical inventory**. CI remains the authoritative executable check for the exact tree.

The CEQAnet HTTP 403 is preserved as an external access limitation and verified-promotion blocker. It is not treated as a defect to bypass.

## Resolved defect ledger

| ID | Severity | Area | Prior defect | Resolution |
|---|---|---|---|---|
| CS-AUDIT-001 | P1 | Persistence docs | Movement and identity persistence was marked missing. | Dedicated ORM/store coverage exists and documentation is reconciled. |
| CS-AUDIT-002 | P2 | Architecture docs | Lead dedupe, workflow, and result documentation was stale. | Dedicated architecture and status documentation exists. |
| CS-AUDIT-003 | P2 | README | Broad limitations understated implemented persistence and operator scope. | Language is narrowed and certification guards future drift. |
| CS-AUDIT-004 | P1 | Lead persistence | Post-enrichment workflow records lacked dedicated storage. | Indexed fields and full payloads are persisted. |
| CS-AUDIT-005 | P1 | Parcel persistence | Parcel core and site-resolution results lacked dedicated storage. | Dedicated storage and round-trip validation exist. |
| CS-AUDIT-006 | P1 | Enrichment | Scoring weights lacked profile version identity. | Versioned profile identity is persisted with reports. |
| CS-AUDIT-007 | P1 | Workflow | Status events lacked a transition matrix. | Matrix enforcement and final-state immutability exist. |
| CS-AUDIT-008 | P1 | Result ledger | Share uncertainty existed only in limitation prose. | Explicit share states are modeled and persisted. |
| CS-AUDIT-009 | P1 | Source maturity | Seed records, reachability, contracts, and verified usable sources could be conflated. | Layered maturity governance separates each class. |
| CS-AUDIT-010 | P1 | Registry apply | Source planning lacked a safe execution boundary. | Digest-bound, evidence-backed, status-only controlled apply exists. |
| CS-AUDIT-011 | P1 | Workflow event identity | Repeated transition cycles could reuse an event ID and overwrite history. | Sequence participates in identity; collisions are rejected and tested. |
| CS-AUDIT-012 | P1 | Result authority | Differing outcomes lacked immutable correction and concurrency doctrine. | Linear immutable revisions, exact-state authority heads, and append-only events exist. |
| CS-AUDIT-013 | P2 | Lead operator exposure | Persisted post-enrichment records lacked consolidated inspection/action access. | Lead list/detail, transition inspection, and governed transition commands exist. |
| CS-AUDIT-014 | P1 | Upstream operator boundary | Upstream records lacked consolidated inspection, while generic mutation could bypass provenance. | Full-payload read access exists and generic mutation is blocked. |
| CS-AUDIT-015 | P1 | Result compatibility | New numeric constraints could invalidate historical persisted rows. | New writes are strict while legacy payloads remain readable. |
| CS-AUDIT-016 | P1 | Parcel topology | Envelope-only matching allowed concavity and hole false positives. | Ring-preserving topology is used for supported geometry. |
| CS-AUDIT-017 | P1 | Geometry format/centroid/CRS | WKT was unparsed, centroids used coordinate averages, and projected coordinates could be treated as geographic. | Shared parsing, area-weighted source-plane centroids, CRS conflict preservation, and direct-comparison refusal exist. |
| CS-AUDIT-018 | P1 | Governance metadata | Standing doctrine and PR validation references became stale. | Doctrine issue and historical PR metadata are reconciled through GitHub API. |
| CS-AUDIT-019 | P1 | Certification coverage | CI did not independently scan every tracked file or reject suppressions, skipped tests, transient files, broken links, invalid entrypoints, secrets, and dirty worktrees. | Permanent `constructionsight-certify` and hardened CI gates cover the complete tracked tree. |
| CS-AUDIT-020 | P1 | Defect classification | Planned capabilities were labeled as partially fixed defects. | Resolved defects and planned capabilities are separate canonical ledgers. |
| CS-AUDIT-021 | P1 | CEQAnet query truth | `text_terms` counted as a bounding query filter even though the verified advanced-search request builder did not transmit them. | Both listing and recurring-run query models reject free-text terms, preventing false restriction claims. |
| CS-AUDIT-022 | P1 | CEQAnet execution evidence | Recurring-run executions initially had field-level semantic checks but no digest over the complete retained response envelope. | Exact execution schemas and a canonical execution digest bind bodies, URLs, queries, counts, flags, identities, and the no-persistence assertion before semantic verification. |
| CS-AUDIT-023 | P1 | CEQAnet evidence-phase tree | PR #93 merged temporary collector/workflow files while its claimed evidence files were absent. | Evidence and audit artifacts are committed, the canonical CI file is restored, temporary tooling is deleted, and the branch is re-certified before replacement merge. |
| CS-AUDIT-024 | P1 | CEQAnet observation logic | Brittle text markers and a robots media-type assumption rejected valid source behavior and obscured the true access boundary. | Official page shapes and policies were reviewed, diagnostic failures are preserved, HTTP 403 is treated as a blocker, and no bypass is permitted. |
| CS-AUDIT-025 | P1 | CEQAnet CSV encoding | The first live CSV proof returned valid source bytes containing Windows-1252 data that the UTF-8-only parser rejected. | Strict UTF-8 remains preferred; explicit Windows-1252 fallback is digest-visible, tested, and used to derive a separately verified replay from the original retained body without network access. |
| CS-AUDIT-026 | P1 | Replay final-tree integrity | PR #100 left two write-enabled replay workflows and two patch scripts in the production tree after their runtime changes had already landed. | PR #101 deletes all temporary replay machinery, tests complete absence, restores canonical CI-only validation, and certifies the exact cleaned tree. |

## Planned capability ledger

These are intentionally absent capabilities, not defects in the currently supported boundary.

| ID | Planned capability | Current guard | Entry condition |
|---|---|---|---|
| CS-PLAN-001 | Optional preview archives and nested child tables | Core persisted records remain lossless; report/config layers are explicitly ephemeral. | Add only when replay or query requirements justify schema expansion. |
| CS-PLAN-002 | Verified recurring live source adapters | CEQAnet is `partial`; a digest-bound policy and sequence-1 series head govern bounded evidence through 2026-08-13. One project observation passed on UTC 2026-07-14 with one GET, zero retries, complete-body retention, full-chain recomputation, and independent verification. HTML automation remains blocked by HTTP 403; no production scheduler exists. | Collect and independently verify three additional successful observations on later unused UTC dates, including document scope, before a separate promotion review. |
| CS-PLAN-003 | CRS transformation, projection-aware/geodesic calculations, and topology repair | Incompatible CRS is preserved and refused; no survey-grade conclusion is emitted. | Pin a GIS stack and define transformation provenance, axis order, grid behavior, accuracy, failure, and repair doctrine. |
| CS-PLAN-004 | Domain-specific upstream correction actions | Generic mutation is unavailable. | Define record-family-specific stale-state, correction, supersession, provenance, and audit behavior. |
| CS-PLAN-005 | Workflow reopen/override | Final states have no outgoing transitions. | Define explicit authority, reason, stale-state, and append-only event rules. |
| CS-PLAN-006 | Outreach preview and sending | No sending path exists. | Implement human preview, explicit approval, duplicate suppression, compliance, evidence, and delivery audit first. |
| CS-PLAN-007 | GUI/operator application | CLI and service boundaries remain authoritative. | Build after source maturity and operator workflows justify exposure. |

## Current source maturity

| Stage | Canonical status |
|---|---|
| Canonical source records | One CEQAnet record is `partial`; three records remain unverified. |
| Readiness/audit/checklist evidence | Report/file-backed workflows exist; CEQAnet has a committed browser-review evidence packet. |
| Official CSV contract | Deterministic planning, one no-retry HTTP 200 proof, and a verified Windows-1252 offline replay of the exact retained body exist. |
| Source-maturity proposal | Offline digest-bound build/verify commands preserve `keep_partial` and cannot authorize registry mutation or recurring execution. |
| Official-CSV access policy | Canonical policy digest `d84e6b80234a96799593db0601cc92e6480bad15bfd016001b35568c481c1674` is effective 2026-07-14 through 2026-08-13; policy verification passes, while production authority and source promotion remain false. |
| Official-CSV evidence series | The network-free sequence-0 root digest is `b2a18770ec5ca28dfb907ce74b0b5ba120e6bb028ee35e3acd5188d42c182634`. Sequence-1 digest `a6f6e548d675ee9716822fef87cc02d8a4d169f16ab151bae0f297321b8c07df` independently verifies with one successful project observation, status `collecting`, and no maturity-review readiness. |
| Promotion/update planning | Deterministic dry-run plans and approval digests exist. |
| Controlled registry apply | Evidence-gated status-only apply exists. |
| Verified usable source | Zero in the canonical registry. |
| Contract-ready adapters | Registered families exist; no coverage claim follows. |
| Guarded live read-only execution | Limited executors and recurring-run governance exist; the `partial` CEQAnet source remains blocked by the verified-only gate. |
| Production recurring integration | Not established. |

A prior report-only HTTP observation classified CEQAnet as `cross_host_redirect`, CSLB as `no_redirect`, San Bernardino EZOP as `same_host_redirect`, and Riverside PLUS as `downgraded_to_http`. The later CEQAnet review observed official pages and CSV links, while bounded automation eventually received HTTP 403. Neither the offline CSV contract, reachability, nor partial maturity establishes verified recurring coverage.

## Persistence coverage

| Layer | Persistence truth |
|---|---|
| Domain and intelligence records | First-generation ORM/store coverage exists. |
| Source registry | Seed/config plus controlled file-backed apply. |
| Readiness/audit/checklist/plans | Report/file-backed by design. |
| CEQAnet source evidence | Versioned JSON evidence, checklist JSON, and Markdown audit are committed; raw response bodies are not represented as archived evidence. |
| CEQAnet CSV inspections/executions/replays | Schema-versioned offline inspections, live-proof envelopes, and derived encoding replays may be written by the operator CLI; no database write, attachment download, retry, or schedule is authorized. |
| CEQAnet maturity proposals | Schema-versioned proposal and verification JSON plus a Markdown audit are artifact-only; the fixed decision is `keep_partial`, and all mutation/recurring authority remains false. |
| CEQAnet CSV access policy | Schema-versioned policy and independent verification JSON plus a Markdown audit are artifact-only. They bind the exact registry, proposal, original execution, and replay digests; no response body, database state, scheduler state, or production authority is created by policy issuance. |
| CEQAnet CSV evidence series | Schema-versioned policy-bound execution artifacts retain complete live envelopes; compact immutable series and independent verification JSON plus Markdown audits bind repo-relative references, sequence, predecessor, and digests. The current head contains one observation; no database or scheduler state is implied. |
| Source apply reports | Required JSON audit with digests and row-level outcomes. |
| CEQAnet recurring-run definitions/manifests/executions | Exact-schema digest-bound JSON artifacts only; no attempt ledger or scheduler state is implied. |
| Parcel preview layers | Report/config-backed and intentionally ephemeral. |
| Parcel core/site resolution | Indexed fields plus full payload, raw geometry, hashes, CRS, and compatible summaries. |
| Permit snapshots/transitions | Indexed fields plus full payload. |
| Contractor identities | Indexed fields plus full payload. |
| Decision records | Indexed fields plus full payload. |
| Enrichment/review/dedupe | Indexed operational fields plus full payload. |
| Lead workflows/events | Indexed status/event fields plus append-only full history. |
| Result ledgers/shares | Immutable append-only revisions with full-history validation. |
| Result authority heads/events | Unique compare-and-swap head plus immutable operator events; the head is control state, not evidence replacement. |

Persistence is valid only when mapping is deliberate and preserves reasons, confidence, limitations, provenance, unknown fields, and future-compatible full payloads.

## Operator exposure

| Area | Exposure |
|---|---|
| Core intake, opportunity, gap, parcel preview, site resolution, and storage summary | Present. |
| Source status/readiness/audit/checklist/plan/apply | Present with evidence and mutation boundaries. |
| CEQAnet source evidence | Committed browser-review evidence, policy conclusion, CSV-link inventory, and automation diagnostics are present. |
| CEQAnet official CSV contract | `plan`, `inspect-file`, `execute-live`, and `verify-execution` expose offline planning/inspection, one explicit proof GET, and offline verification. |
| CEQAnet fixture-to-archive tooling | Present and guarded. |
| CEQAnet recurring-run artifacts and attempts | Definition, manifest, execute, and digest-aware verify commands exist; `partial` source maturity remains blocked. |
| CEQAnet maturity proposal | Offline build/verify commands bind current evidence and emit only a non-authorizing `keep_partial` proposal. |
| CEQAnet CSV access policy | Offline `build`, `verify`, and `check-current` commands enforce exact evidence bindings, the maximum 31-day authority window, expiration, conservative controls, and independent verification. They do not perform network requests. |
| CEQAnet CSV evidence series | Offline `build`/`verify` commands and one explicitly authorized `execute` command expose full policy/ledger preflight, exact daily limits, complete execution retention, terminal halts, and report-only readiness. Sequence 1 is committed; the daily gate prohibits another UTC 2026-07-14 request. |
| Upstream records | Full-payload list/detail only. |
| Lead records | Consolidated list/detail plus governed workflow transitions. |
| Result authority | Validated current/history plus explicit exact-state record/correction. |
| Repository certification | Complete tracked-tree audit command. |
| Generic upstream mutation | Absent by design. |
| Outreach sending | Absent. |
| GUI | Absent. |

## Limitation and uncertainty preservation

Where applicable, the architecture must preserve:

- reasons, limitations, confidence, and review-needed state;
- source keys, source record IDs, full normalized payloads, provenance, and evidence references;
- lawful-access, browser-versus-automation, policy-review, and source-maturity boundaries;
- exact CSV request/final URL identity, status, headers, complete response bytes, body length/hash, media type, encoding, canonical roles, unknown columns, row counts, truncation, retained rows, inspection digest, retry count, and live execution digest;
- source registry/checklist digests, recurring-run definition/manifest/execution identities, exact windows, attempt identity, complete retained execution-envelope digest, and stale-evidence findings;
- maturity-proposal registry, live execution, response body, replay, inspection, decision, blocker, and authority bindings;
- CSV access-policy digest, effective and expiry dates, official host/path, export scopes, method, request/day/retry/timeout/size limits, complete-body retention, independent verification, per-execution authorization, halt statuses, evidence-series requirements, forbidden behaviors, and production blockers;
- evidence-execution authorization time/date, request count, policy controls, complete live envelope and verification, artifact reference, execution/observation/series digests, series sequence/predecessor, successful dates/scopes, status, halt/readiness finality, row-retention bound, and non-authority fields;
- HTTP access failures, robots uncertainty, no-bypass decisions, and official export-surface observations;
- unknown and unmapped fields;
- raw geometry, format, embedded/supplied CRS, conflicts, coordinate bounds, topology method, rings, holes, validity limitations, centroid limitations, fallback reasons, and non-survey-grade boundaries;
- workflow transitions, event sequence, unique identity, and stale-state expectations;
- result share uncertainty, immutable revision chain, predecessor, correction reason, authority head, and authority events; and
- source plan/apply digests and row-level audit outcomes.

These fields are evidentiary controls, not cleanup noise.

## Forward enforcement

Every feature PR must reconcile runtime, tests, documentation, persistence, operator exposure, lawful access, provenance, compatibility, source maturity, and planned-capability boundaries. The complete certification matrix must pass on the exact final head. No PR may merge with a known defect, executable audit finding, unresolved review thread, stale status claim, hidden suppression, skipped test, unreviewed mutation boundary, or temporary write-enabled workflow left in the production tree.
