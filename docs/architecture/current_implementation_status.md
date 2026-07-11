# Current Implementation Status

This document reconciles implemented ConstructionSight layers with documentation, persistence, CLI exposure, live source status, and known limitations.

## Status labels

- `implemented`: model/service logic exists in `src/constructionsight`.
- `tested`: dedicated tests exist in `tests`.
- `documented`: architecture documentation exists.
- `persisted`: SQLAlchemy ORM/store coverage exists.
- `cli`: an operator-facing command exists.
- `live_source_integrated`: live lawful source execution is implemented and represented as live.
- `planned`: identified but not implemented.

## Pipeline status

| Layer | Implemented | Tested | Documented | Persisted | CLI | Live source integrated | Status note |
|---|---:|---:|---:|---:|---:|---:|---|
| Lawful intake boundary | Yes | Yes | Yes | Partial | Yes | No | Public-access boundary is documented and tested through intake/adapter contracts. |
| Source registry | Yes | Yes | Yes | Yes | Yes | No | Seed records remain unverified until checked; controlled apply can change only an approved evidence-backed verification status and does not create live coverage. |
| Source readiness workflow | Yes | Yes | Yes | No | Yes | No | Report-only readiness workflow preserves source identity, lawful boundary, adapter/source state, optional HTTP reachability, reasons, limitations, and next action without mutating registry status. |
| Source audit package | Yes | Yes | Yes | No | Yes | No | Report-only audit package preserves original/final URLs, HTTP status, redirect classification, source/adapter/readiness state, reasons, limitations, and next action before registry review. |
| Source verification checklist | Yes | Yes | Yes | No | Yes | No | Report-only manual checklist records entry, query, list, detail, access-barrier, terms-review, notes, and evidence references without changing registry status. |
| Source plan reports | Yes | Yes | Yes | No | Yes | No | Dry-run source plan commands produce review actions, proposed registry payloads, evidence references, complete ordered-registry digests, and deterministic approval digests. |
| Source registry controlled apply | Yes | Yes | Yes | File-backed | Yes | No | Explicit `--apply` workflow validates the complete registry snapshot, plan digest, derived counts, evidence, status-only mutation, canonical identity, distinct paths, required audit output, and target-last atomic replacement. No current seed source is promoted by this implementation. |
| Adapter contracts | Yes | Yes | Yes | N/A | Yes | No | Most adapter families remain placeholder contracts; source-status reporting prevents adapter contracts from being mistaken for live coverage. |
| Universal intake | Yes | Yes | Yes | Partial | Yes | No | Source-neutral records and routing exist; live source breadth is limited. |
| Opportunity transition intake | Yes | Yes | Yes | Partial | Yes | No | Converts intake facts into opportunity candidates. |
| Shovels/Regrid gap alignment | Yes | Yes | Yes | N/A | Yes | No | Planning and gap matrix exists; not a claim of platform parity. |
| Parcel/site resolution | Yes | Yes | Yes | Yes | Yes | No | Hint-based and parcel-backed resolution exist with confidence, limitations, dedicated result storage, storage-summary visibility, and read-only upstream list/detail access. |
| Parcel source registry | Yes | Yes | Yes | No | Yes | No | Tracks source targets; does not import live parcel coverage. |
| Parcel schema preview | Yes | Yes | Yes | No | Yes | No | Pre-import schema gate exists. |
| Parcel row preview | Yes | Yes | Yes | No | Yes | No | Pre-record row gate exists. |
| Parcel core record | Yes | Yes | Yes | Yes | Yes | No | Canonical parcel records are persisted and exposed through read-only upstream list/detail commands; live import remains pending. |
| Geometry normalization | Yes | Yes | Yes | Payload | Partial | No | Geometry remains available through parcel payloads; topology-grade calculations and dedicated geometry actions remain pending. |
| Parcel-backed site resolution | Yes | Yes | Yes | Yes | Yes | No | Persisted resolution reports are exposed read-only with candidates, conflicts, reasons, and limitations preserved; envelope-only containment can overmatch. |
| Permit snapshot transition spine | Yes | Yes | Yes | Yes | Yes | No | Persisted snapshots and transitions have read-only list/detail access; recurring live adapters and domain-specific write actions remain pending. |
| Contractor identity | Yes | Yes | Yes | Yes | Yes | No | Persisted identities have read-only list/detail access; CSLB live verification and domain-specific correction actions remain pending. |
| Decision record | Yes | Yes | Yes | Yes | Yes | No | Persisted decision records have read-only list/detail access; agenda/staff-report adapters and domain-specific write actions remain pending. |
| Opportunity enrichment | Yes | Yes | Yes | Yes | Yes | No | Versioned scoring reports are persisted and exposed through consolidated lead list/detail commands. |
| Lead review package | Yes | Yes | Yes | Yes | Yes | No | Review packages are persisted and exposed through consolidated lead list/detail commands. |
| Lead dedupe | Yes | Yes | Yes | Yes | Yes | No | Fingerprints and duplicate results are persisted and exposed through consolidated lead list/detail commands. |
| Lead workflow status | Yes | Yes | Yes | Yes | Yes | No | Operator commands expose list/detail, allowed transitions, and explicit stale-state-protected matrix-valid transitions with append-only event persistence. |
| Result ledger/share calculation | Yes | Yes | Yes | Yes | Yes | No | Ledger/share list and detail access preserve explicit share states. Mutation remains intentionally withheld until authoritative outcome history/replacement doctrine is defined. |
| Outreach preview | No | No | No | No | No | No | Planned only; no external action should be implied. |
| UI/operator app | No | No | No | No | No | No | Planned only. |

## Defect ledger

| ID | Severity | Layer | File(s) | Observed fact | Why it matters | Root cause | Recommended fix | Disposition |
|---|---|---|---|---|---|---|---|---|
| CS-VIAM-001 | P1 | Doctrine | `README.md` | README previously lagged the newer post-parcel layers. | Runtime and doctrine drift apart. | Rapid implementation outpaced docs. | Keep README linked to the canonical implementation-status matrix and audit inventory. | Fixed; monitor forward. |
| CS-VIAM-002 | P1 | Persistence | `src/constructionsight/storage/*` | Movement/identity, post-enrichment lead workflow, parcel core, and site-resolution report layers now have dedicated ORM/store coverage. Optional preview archives and some nested child tables remain intentionally unimplemented. | Remaining gaps are now narrower and should not be confused with missing core persistence. | Architecture-first implementation sequence. | Add optional archives or child tables only when query requirements justify them. | Partially fixed; narrow remaining backlog. |
| CS-VIAM-003 | P1 | Source maturity | `source_status_report.py`, `source_readiness_*`, `audit_package_cli.py`, `source_verification_*`, `source_promotion_plan_*`, `source_registry_integrity.py`, `source_registry_update_plan_*`, `source_registry_apply_*`, `data/source_registry.seed.json` | Source maturity layers now separate registry claims, adapter maturity, reachability, redirect evidence, manual observations, dry-run actions, complete registry snapshots, proposed payloads, approval digests, and controlled status-only apply results. | Product must not overclaim source readiness or allow an unreviewed or stale registry mutation. | Source records and adapter contracts originally lacked a complete evidence-to-apply governance chain. | Keep apply evidence-gated, full-snapshot-bound, digest-approved, status-only, path-safe, auditable, and distinct from live-integration claims. | Fixed; monitor forward. |
| CS-VIAM-004 | P1 | Adapter maturity | `src/constructionsight/adapters/specs.py` | Most adapter families are placeholders; CEQAnet is contract-ready, not live production coverage. | Avoid false live-integration claims. | Adapter contracts preceded live adapters. | Use source-status, readiness, audit, checklist, planning, and controlled apply governance before making coverage claims. | Partially fixed; live maturity still backlog. |
| CS-VIAM-005 | P1 | Geometry | `parcel_geometry.py`, `parcel_site_resolution.py` | Geometry parsing now removes simple closing-ring duplication, supports GeoJSON Feature payloads, preserves polygon centroid approximation limits, and propagates envelope-only containment limits into parcel-backed site candidates. | Prevents geometry-derived candidates from being overstated as survey-grade boundary proof. | Dependency-light first implementation. | Add topology-grade point-in-polygon and projection-aware calculations later. | Partially fixed; topology still backlog. |
| CS-VIAM-006 | P1 | Scoring | `opportunity_enrichment_service.py`, `opportunity_scoring_profile.py` | Opportunity enrichment now uses a versioned default scoring profile and records profile key/version in reports. | Future tuning can preserve old report semantics instead of silently changing score meaning. | First-pass scoring implementation was hardcoded. | Add additional profile versions only with explicit doctrine and tests. | Fixed; monitor forward. |
| CS-VIAM-007 | P1 | Workflow | `lead_workflow_service.py`, `lead_workflow_rules.py` | Lead workflow status moves are constrained by a transition matrix and final statuses have no outgoing moves. | Prevents invalid operational state jumps while preserving append-only event history. | Initial workflow model prioritized audit events. | Add any future override/reopen behavior only with explicit doctrine and tests. | Fixed; monitor forward. |
| CS-VIAM-008 | P1 | Result ledger | `result_ledger_models.py`, `result_ledger_service.py` | Won results can now explicitly distinguish pending gross value, pending share rate, and calculated share. | Pending-share uncertainty is queryable and no longer hidden only in limitation text. | Share-rate uncertainty was preserved but not structurally represented. | Add future business-specific enforcement only after explicit review. | Fixed; monitor forward. |
| CS-VIAM-009 | P2 | CLI | `pyproject.toml`, `lead_operator_*`, `upstream_operator_*` | Persisted post-enrichment and upstream core records now have consolidated list/detail commands; workflow transitions remain explicitly governed. | Operators can inspect the implemented pipeline without editing observed or derived evidence through generic commands. | Model/service/storage-first implementation. | Add only domain-specific upstream write actions that call canonical builders and define stale-state, correction, supersession, and audit behavior. | Fixed for read access; write actions remain deliberate backlog. |
| CS-VIAM-010 | P2 | Documentation | `docs/architecture/*` | Lead and upstream operator docs now exist and are represented in the status matrix. | Status matrix must not remain stale after documentation lands. | Rapid implementation outpaced matrix reconciliation. | Keep status matrix synchronized with documentation/runtime. | Fixed. |
| CS-VIAM-011 | P1 | Workflow event identity | `lead_workflow_models.py`, `lead_workflow_service.py`, `storage/lead_workflow_store.py` | Repeating the same valid transition and reason after a workflow cycle could reuse an event ID and upsert over earlier history. | Event identity collision could destroy append-only audit history. | Event IDs omitted workflow event sequence. | Include sequence in event identity, reject duplicate event IDs, and test repeated persisted cycles. | Fixed. |
| CS-VIAM-012 | P1 | Result ledger authority | `result_ledger_service.py`, `storage/lead_workflow_store.py` | Deterministic ledger IDs include outcome status, allowing multiple differing outcome rows for one workflow without explicit supersession doctrine. | A mutable operator command could create contradictory authoritative outcomes. | Result modeling preceded correction/history governance. | Keep ledger/share operator access read-only until authoritative current-state or append-only supersession doctrine is defined and tested. | Open; mutation deliberately blocked. |
| CS-VIAM-013 | P1 | Upstream evidence mutation | `upstream_operator_*`, movement/identity and parcel/site stores | Generic edits to permit, contractor, decision, parcel, or site-resolution rows would bypass their source-specific domain builders. | Direct edits could sever provenance, confidence, geometry, transition, and limitation semantics. | Persistence existed before a consolidated operator surface. | Keep the consolidated upstream command read-only; introduce writes only through domain-specific governed actions. | Controlled; read access implemented and generic mutation blocked. |

## Forward cleanup rule

Every future feature PR must update this matrix or explicitly state why no status changed. A new model or service must not silently bypass documentation, tests, persistence review, CLI review, and limitation/provenance review.

See `docs/audits/full_repo_audit_inventory.md` for the canonical full-repo audit inventory.
