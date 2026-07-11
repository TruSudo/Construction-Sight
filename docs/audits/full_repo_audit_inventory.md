# Full-Repo Audit Inventory

This audit reconciles the current ConstructionSight repository after controlled source-registry apply governance, consolidated post-enrichment lead operator tooling, and read-only upstream record access.

## Executive status

ConstructionSight has a substantial tested model/service architecture for lawful public-record construction intelligence. Implemented strengths include source-neutral intake, guarded CEQAnet tooling, parcel/site reasoning, permit movement, contractor identity, decision records, versioned opportunity enrichment, lead review and dedupe, matrix-constrained workflow status, result ledger/share-state modeling, layered source-governance reporting, controlled registry-status apply, dedicated persistence, storage-summary reporting, post-enrichment lead operator tooling, and read-only access to persisted upstream records.

This is not yet a production live-source platform. Most adapter families remain contract-ready or placeholder contracts, not verified recurring integrations. CEQAnet has guarded operator/archive tooling but is not production-grade recurring coverage. Controlled registry apply changes only an approved verification-status field and does not establish live coverage.

No external outreach-sending behavior is implemented or implied. A GUI/operator application remains planned.

## Status labels

| Label | Meaning |
|---|---|
| Implemented | Runtime model, service, CLI, or audit logic exists in `src/constructionsight`. |
| Tested | Dedicated test coverage exists in `tests`. |
| Documented | Architecture, doctrine, matrix, or README documentation exists. |
| Persisted | SQLAlchemy ORM/store coverage exists or the layer is deliberately fixture/config-backed. |
| CLI/operator access | A script or Typer command exposes the function to an operator. |
| Live source integrated | Lawful live execution is implemented and documented/tested as live. |
| Planned | Identified but not implemented. |

## Pipeline inventory

| Layer | Implemented | Tested | Documented | Persisted | CLI/operator access | Live source integrated | Known limitation / required cleanup |
|---|---:|---:|---:|---:|---:|---:|---|
| Lawful intake boundary | Yes | Yes | Yes | Partial | Yes | No | Preserve the public-access boundary in every source PR. |
| Source registry | Yes | Yes | Yes | Yes/file-backed | Yes | No | Four seed records remain unverified; perform source-specific evidence review before promotion. |
| Source readiness | Yes | Yes | Yes | No | Yes | No | Report-only; does not mutate verification status. |
| Source audit package | Yes | Yes | Yes | No | Yes | No | Preserves URL/HTTP/redirect evidence but does not replace manual verification. |
| Source verification checklist | Yes | Yes | Yes | No | Yes | No | Operator observations remain evidence-backed file/report records. |
| Source promotion/update planning | Yes | Yes | Yes | No | Yes | No | Dry-run-first and limited to proposed verification-status changes. |
| Controlled source registry apply | Yes | Yes | Yes | File-backed | Yes | No | Requires complete-registry and plan digests, evidence, status-only mutation, path separation, audit output, and explicit authorization. |
| Adapter contracts | Yes | Yes | Yes | N/A | Yes | No | Contracts are not equivalent to live recurring integrations. |
| CEQAnet guarded tooling | Yes | Yes | Yes | Partial | Yes | Limited/guarded | Complete source verification and recurring-run governance before stronger claims. |
| Universal intake | Yes | Yes | Yes | Partial | Yes | No | Unknown/unmapped fields remain explicit; source breadth is limited. |
| Opportunity transition intake | Yes | Yes | Yes | Partial | Yes | No | Candidate conversion is not an outreach system. |
| External intelligence/gap spine | Yes | Yes | Yes | N/A | Yes | No | Capability modeling is not platform parity. |
| Parcel source/schema/row preview | Yes | Yes | Yes | Config/report-backed | Yes | No | Add persisted import-batch audit only when live ingestion begins. |
| Parcel core record | Yes | Yes | Yes | Yes | Read-only | No | List/detail access exists; verified live import and domain-specific correction actions remain pending. |
| Geometry normalization | Yes | Yes | Yes | Payload | Partial | No | Geometry is preserved in parcel payloads; topology and projection-aware calculations remain backlog. |
| Parcel-backed site resolution | Yes | Yes | Yes | Yes | Read-only | No | List/detail access preserves candidates, conflicts, and limitations; envelope containment can overmatch. |
| Permit transition spine | Yes | Yes | Yes | Yes | Read-only | No | Snapshot and transition list/detail access exists; recurring live adapters and governed write actions remain pending. |
| Contractor identity | Yes | Yes | Yes | Yes | Read-only | No | Identity list/detail access exists; CSLB live verification and governed correction actions remain pending. |
| Decision records | Yes | Yes | Yes | Yes | Read-only | No | Decision list/detail access exists; agenda/staff-report adapters and governed write actions remain pending. |
| Opportunity enrichment | Yes | Yes | Yes | Yes | Yes | No | Versioned scoring is persisted and exposed through lead list/detail commands. |
| Lead review package | Yes | Yes | Yes | Yes | Yes | No | Full payload, reasons, limitations, and score remain operator-visible. |
| Lead dedupe | Yes | Yes | Yes | Yes | Yes | No | Fingerprints and duplicate results are available through list/detail commands. |
| Lead workflow status | Yes | Yes | Yes | Yes | Yes | No | List/detail, allowed-transition inspection, and explicit stale-state-protected transitions exist. |
| Result ledger/share calculation | Yes | Yes | Yes | Yes | Read-only | No | Mutation is blocked until authoritative outcome correction/supersession doctrine exists. |
| Outreach preview/sending | No | No | No | No | No | No | Planned only; no external action is implied. |
| GUI/operator application | No | No | No | No | No | No | Planned only. |

## Current observed source-audit outcome

A report-only HTTP audit against `data/source_registry.seed.json` observed:

| Source | Redirect classification | Recommendation |
|---|---|---|
| CEQAnet State Clearinghouse | `cross_host_redirect` | `keep_unverified_reachable` |
| CSLB Public License Search | `no_redirect` | `keep_unverified_reachable` |
| San Bernardino County EZOP | `same_host_redirect` | `keep_unverified_reachable` |
| Riverside County PLUS Online | `downgraded_to_http` | `keep_unverified_reachable` |

All four URLs were reachable in that observation, but all four records remain unverified. Neither the audit package nor controlled apply promotes a source without reviewed evidence.

## Contradiction and defect ledger

| ID | Severity | Area | Observed issue | Runtime truth / disposition |
|---|---|---|---|---|
| CS-AUDIT-001 | P1 | Persistence docs | Movement/identity persistence was previously marked missing. | Dedicated ORM/store coverage exists; fixed. |
| CS-AUDIT-002 | P2 | Architecture docs | Lead dedupe/workflow/result documentation status was stale. | Dedicated docs exist; fixed. |
| CS-AUDIT-003 | P2 | README | Broad limitations understated newer persistence coverage. | Language narrowed; monitor forward. |
| CS-AUDIT-004 | P1 | Lead persistence | Post-enrichment workflow records were listed as pending storage. | Dedicated ORM/store coverage exists; fixed. |
| CS-AUDIT-005 | P1 | Parcel persistence | Parcel core/site-resolution records were listed as pending. | Dedicated storage exists; fixed. |
| CS-AUDIT-006 | P1 | Enrichment | Scoring weights were not profile-versioned. | Versioned profile identity is persisted; fixed. |
| CS-AUDIT-007 | P1 | Workflow | Status events lacked a transition matrix. | Matrix enforcement and final-state immutability exist; fixed. |
| CS-AUDIT-008 | P1 | Result ledger | Share uncertainty existed only in limitation text. | Explicit share-state fields exist and persist; fixed. |
| CS-AUDIT-009 | P1 | Source maturity | Seed records and adapter contracts could be mistaken for verified sources. | Layered status/readiness/audit/checklist/apply governance separates maturity; fixed. |
| CS-AUDIT-010 | P1 | Registry apply | Planning lacked a safe execution boundary. | Digest-bound, evidence-backed, status-only controlled apply exists; fixed. |
| CS-AUDIT-011 | P1 | Workflow event identity | Repeating the same valid transition and reason after a cycle could reuse an event ID and overwrite prior event history. | Event identity includes workflow sequence; models reject duplicate IDs; repeated persisted cycles are tested; fixed. |
| CS-AUDIT-012 | P1 | Result authority | Ledger IDs include outcome status, permitting differing outcome rows for one workflow without supersession doctrine. | Operator ledger/share access remains read-only. Mutation is deliberately blocked pending authoritative current-state or append-only supersession rules; open. |
| CS-AUDIT-013 | P2 | Lead operator exposure | Persisted post-enrichment records lacked consolidated list/detail/action access. | `constructionsight-leads` exposes list/detail, allowed transitions, and governed workflow transitions; fixed. |
| CS-AUDIT-014 | P1 | Upstream operator boundary | Permit, contractor, decision, parcel, and site-resolution rows lacked consolidated inspection, while generic mutation would bypass their domain semantics. | `constructionsight-upstream` exposes full-payload list/detail access only. Unsupported filters and malformed payloads fail explicitly; generic mutation remains blocked. |

## Persistence coverage ledger

| Layer | Persistence truth | Notes |
|---|---|---|
| Domain and intelligence records | Persisted | First-generation ORM/store coverage exists. |
| Source registry | Persisted/config-backed | Seed/config storage plus file-backed controlled apply. |
| Source readiness/audit/checklist/plans | Report/file-backed | Persist only if replay requirements justify dedicated tables. |
| Source apply reports | Required JSON audit | Includes plan/registry digests and row-level evidence. |
| Parcel preview layers | Report/config-backed | Generally ephemeral. |
| Parcel core/site-resolution | Persisted | Indexed fields plus complete JSON payloads. |
| Permit snapshots/transitions | Persisted | Indexed fields plus complete JSON payloads. |
| Contractor identities | Persisted | Indexed fields plus complete JSON payloads. |
| Decision records | Persisted | Indexed fields plus complete JSON payloads. |
| Opportunity enrichment | Persisted | Score/confidence/profile identity plus complete payload. |
| Lead review/dedupe | Persisted | Indexed review/dedupe fields plus complete payloads. |
| Lead workflows/events | Persisted | Indexed status/event fields plus complete payload and event history. |
| Result ledgers/shares | Persisted | Indexed outcome/share state plus complete payloads. |

Persistence rule: generic tables are not equivalent to source-neutral models unless mapping is deliberate, lossless, and preserves full payloads, reasons, confidence, limitations, provenance, and future fields.

## CLI/operator exposure ledger

| CLI/script area | Runtime exposure | Notes |
|---|---|---|
| Core intake, opportunity, gap, parcel preview, site resolution, and storage summary | Present | Existing operator surfaces remain available. |
| Source status/readiness/audit/checklist/plan/apply | Present | Evidence and controlled mutation boundaries remain explicit. |
| CEQAnet tooling | Present | Guarded fixture-to-archive command family exists. |
| Consolidated upstream operator CLI | Present, read-only | `constructionsight-upstream` exposes permit snapshots/transitions, contractor identities, decision records, parcel core records, and site-resolution results. |
| Consolidated lead operator CLI | Present | `constructionsight-leads` exposes enrichment, review, fingerprint, duplicate, workflow, event, ledger, and share records. |
| Workflow transition action | Present | Requires `--apply`, expected current status, nonblank reason, payload/index integrity, and matrix-valid next status. |
| Ledger/share mutation | Absent by design | Read-only until authoritative outcome correction/history doctrine is defined. |
| Upstream generic mutation | Absent by design | Observed and derived records may be changed only through future domain-specific governed actions. |
| Outreach sending | Absent | No external sending behavior is implemented or implied. |
| GUI/operator app | Absent | Planned only. |

## Source maturity ledger

| Maturity stage | ConstructionSight status |
|---|---|
| Seed source | Four unverified records remain in `data/source_registry.seed.json`. |
| Readiness/audit/checklist evidence | Report-only workflows exist. |
| Promotion/update plan | Dry-run plan and deterministic approval digest exist. |
| Controlled registry apply | Evidence-gated status-only file apply exists. |
| Verified usable source | Current canonical state remains zero verified usable sources. |
| Contract-ready adapter | Registered families exist; this is not a coverage claim. |
| Live read-only integration | Limited/guarded. |
| Production recurring integration | Not established. |
| Operator workflow | Source governance, CEQAnet, preview/audit, storage summary, upstream read-only, and post-enrichment lead workflow commands exist. |

## Limitation and uncertainty preservation check

The architecture must preserve, where applicable:

- reasons and limitations;
- confidence scores or confidence bands;
- source keys, record IDs, and full normalized payloads;
- provenance and evidence references;
- lawful-access boundaries;
- review-needed and unknown/unmapped states;
- workflow status-transition history and unique event identity;
- stale-state expectations for operator mutations;
- result share-state uncertainty;
- source verification and adapter maturity;
- readiness, redirect, recommendation, and next-action evidence;
- plan/apply digests and row-level audit outcomes.

These are evidentiary controls, not cleanup noise. Future PRs must not delete or flatten them merely to simplify models, persistence, CLI output, or tests.

## Forward cleanup enforcement

Every feature PR must update the implementation-status matrix or explicitly state why no status changed. Every new model or service must be reviewed for tests, documentation, persistence, CLI/operator need, lawful-access boundaries, limitation/provenance preservation, and doctrine/runtime impact.

No PR should merge while it knowingly introduces doctrine/runtime drift, stale maturity claims, missing limitations, broken quality gates, or unreviewed persistence/CLI implications.
