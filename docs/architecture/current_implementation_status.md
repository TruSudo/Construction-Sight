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
| Source registry | Yes | Yes | Yes | Yes | Yes | No | CEQAnet is evidence-backed `verified` for guarded manual public reads; the other canonical sources remain `unverified`. Controlled apply changed status only and did not create production coverage. |
| Source readiness workflow | Yes | Yes | Yes | No | Yes | No | Report-only readiness preserves source identity, lawful boundary, adapter/source state, reachability, reasons, limitations, and next action. |
| Source audit package | Yes | Yes | Yes | No | Yes | No | Report-only audit packages preserve URL, HTTP, redirect, maturity, reason, limitation, and next-action evidence. |
| Source verification checklist | Yes | Yes | Yes | No | Yes | No | Manual observations and evidence references do not mutate registry status. |
| Source plan reports | Yes | Yes | Yes | No | Yes | No | Dry-run plans preserve proposed payloads, evidence, complete-registry digests, and deterministic approval digests. |
| Source registry controlled apply | Yes | Yes | Yes | File-backed | Yes | No | Explicit apply validates complete snapshots, digests, evidence, counts, identity, status-only mutation, path separation, audit output, and target-last replacement. |
| Adapter contracts | Yes | Yes | Yes | N/A | Yes | No | Contracts are not represented as verified live integrations. |
| CEQAnet recurring-run governance | Yes | Yes | Yes | Artifact-only | Yes | Guarded only | Exact-schema definitions, manifests, executions, and verifications bind current source evidence, exact windows, attempts, retained response envelopes, and authority. CEQAnet now satisfies the verified/manual-execution gate; every live attempt still requires explicit authorization and permits no persistence. |
| Universal intake | Yes | Yes | Yes | Partial | Yes | No | Source-neutral records and routing exist; live source breadth is intentionally limited. |
| Opportunity transition intake | Yes | Yes | Yes | Partial | Yes | No | Converts intake facts into opportunity candidates without implying outreach. |
| Shovels/Regrid gap alignment | Yes | Yes | Yes | N/A | Yes | No | Capability planning exists; it is not a parity claim. |
| Parcel/site resolution | Yes | Yes | Yes | Yes | Yes | No | Hint and parcel-backed resolution preserve confidence, ambiguity, limitations, storage, topology, and read-only inspection. |
| Parcel source registry | Yes | Yes | Yes | No | Yes | No | Tracks source targets without claiming live parcel coverage. |
| Parcel schema preview | Yes | Yes | Yes | No | Yes | No | Pre-import schema gate exists. |
| Parcel row preview | Yes | Yes | Yes | No | Yes | No | Pre-record row gate exists. |
| Parcel core record | Yes | Yes | Yes | Yes | Yes | No | Raw geometry, hashes, CRS labels, compatible summaries, persistence, and read-only inspection exist. |
| Geometry normalization and topology | Yes | Yes | Yes | Payload | Partial | No | GeoJSON and WKT/EWKT topology, holes, parts, extra dimensions, embedded SRIDs, source-plane area centroids, and conservative CRS refusal exist. |
| Parcel-backed site resolution | Yes | Yes | Yes | Yes | Yes | No | Point and topology matches are distinguished from explicit limited fallback; incompatible CRS is never directly compared to longitude/latitude. |
| Permit snapshot transition spine | Yes | Yes | Yes | Yes | Yes | No | Persisted snapshots and transitions have read-only list/detail access. |
| Contractor identity | Yes | Yes | Yes | Yes | Yes | No | Persisted identities have read-only list/detail access. |
| Decision record | Yes | Yes | Yes | Yes | Yes | No | Persisted decisions have read-only list/detail access. |
| Opportunity enrichment | Yes | Yes | Yes | Yes | Yes | No | Versioned scoring reports are persisted and operator-visible. |
| Lead review package | Yes | Yes | Yes | Yes | Yes | No | Full review payloads, reasons, limitations, and scores remain visible. |
| Lead dedupe | Yes | Yes | Yes | Yes | Yes | No | Fingerprints and duplicate results are persisted and visible. |
| Lead workflow status | Yes | Yes | Yes | Yes | Yes | No | Matrix-valid, exact-state transitions preserve append-only unique events. |
| Result ledger/share authority | Yes | Yes | Yes | Yes | Yes | No | Immutable revisions, serialized exact-state authority, and append-only operator events govern result entry and correction. |
| Repository certification | Yes | Yes | Yes | N/A | Yes | N/A | Every tracked file is scanned; CI enforces dependency integrity, strict lint/type/test gates, warning failure, clean worktree, and diff hygiene. |
| Outreach preview | No | No | No | No | No | No | Planned product capability; no external action is implied. |
| UI/operator app | No | No | No | No | No | No | Planned product capability. |

## Active defect ledger

A certified tree must contain zero active defects. Any new runtime, data-quality, documentation, persistence, provenance, compatibility, security, or CI defect is recorded here immediately and blocks feature work until resolved.

Current active entries: **none recorded**. The executable certification gate remains authoritative for the exact Git tree.

## Resolved defect ledger

Every entry below is resolved within the currently supported scope. Monitoring language is preventive and does not represent an open defect.

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
| CS-VIAM-017 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection tooling instead of the claimed evidence packet and audit report. | The repair phase regenerated and committed current-structure evidence, reviewed official policies, removed all temporary tooling, applied `unverified → verified` through controlled apply, reconciled documentation, and added regression coverage. |

## Planned capability ledger

These entries are future product scope, not defects in the current supported implementation.

| ID | Capability | Current safe boundary | Required entry condition |
|---|---|---|---|
| CS-PLAN-001 | Optional preview archives and nested child tables | Current core records are losslessly persisted; report/config layers remain deliberately ephemeral. | Add only when replay or query requirements justify schema expansion. |
| CS-PLAN-002 | Production recurring live adapters | CEQAnet is verified for guarded manual public-read attempts and has exact-schema definitions, manifests, stale-evidence rejection, digest-bound execution, and full verification. No scheduler or attempt ledger exists. | Prove a reviewed manual run, then define persisted attempt identity, scheduling, retry, archive, observability, rate, and downstream handoff governance. |
| CS-PLAN-003 | CRS transformation, projection-aware/geodesic calculations, and topology repair | Incompatible CRS is preserved and refused rather than guessed; current results are not survey-grade. | Select and pin a GIS stack, define provenance and failure doctrine, and add exact tests. |
| CS-PLAN-004 | Domain-specific upstream corrections | Generic upstream mutation is blocked. | Define source-aware stale-state, correction, supersession, and audit semantics per record family. |
| CS-PLAN-005 | Workflow reopen or override | Final states remain immutable. | Introduce explicit authority, reason, stale-state, and append-only event doctrine. |
| CS-PLAN-006 | Outreach preview and sending | No external sending behavior exists. | Implement preview, approval, dedupe, compliance, evidence, and delivery audit boundaries first. |
| CS-PLAN-007 | GUI/operator application | CLI and persisted services remain the supported operator surface. | Build only after underlying workflows and source maturity justify UI exposure. |

## Forward cleanup rule

Every future feature PR must update this matrix or explicitly state why no status changed. New models and services must not bypass tests, documentation, persistence review, CLI review, lawful-access review, limitation/provenance review, compatibility review, or repository certification.

See [the canonical full-repo audit inventory](../audits/full_repo_audit_inventory.md).
