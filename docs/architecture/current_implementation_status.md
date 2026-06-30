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
| Source registry | Yes | Yes | Yes | Yes | Yes | No | Seed records remain unverified until checked; source-status reporting now separates seed, partial, contract-ready, and verified states. |
| Adapter contracts | Yes | Yes | Yes | N/A | Yes | No | Most adapter families remain placeholder contracts; source-status reporting prevents adapter contracts from being mistaken for live coverage. |
| Universal intake | Yes | Yes | Yes | Partial | Yes | No | Source-neutral records and routing exist; live source breadth is limited. |
| Opportunity transition intake | Yes | Yes | Yes | Partial | Yes | No | Converts intake facts into opportunity candidates. |
| Shovels/Regrid gap alignment | Yes | Yes | Yes | N/A | Yes | No | Planning and gap matrix exists; not a claim of platform parity. |
| Parcel/site resolution | Yes | Yes | Yes | Yes | Yes | No | Hint-based and parcel-backed resolution exist with confidence, limitations, dedicated result storage, and storage-summary visibility. |
| Parcel source registry | Yes | Yes | Yes | No | Yes | No | Tracks source targets; does not import live parcel coverage. |
| Parcel schema preview | Yes | Yes | Yes | No | Yes | No | Pre-import schema gate exists. |
| Parcel row preview | Yes | Yes | Yes | No | Yes | No | Pre-record row gate exists. |
| Parcel core record | Yes | Yes | Yes | Yes | Partial | No | Canonical parcel model and dedicated storage exist; storage-summary visibility exists; live import workflow remains pending. |
| Geometry normalization | Yes | Yes | Yes | Payload | Partial | No | WKT/GeoJSON geometry parsing is hardened with explicit approximation limitations; polygon-grade topology remains pending. |
| Parcel-backed site resolution | Yes | Yes | Yes | Yes | Partial | No | Matches site hints to parcel records, propagates geometry limitations, and persists result reports; envelope-only containment can overmatch. |
| Permit snapshot transition spine | Yes | Yes | Yes | Yes | Partial | No | Source-neutral permit movement model/storage and storage-summary visibility exist; recurring live adapters and action CLIs remain pending. |
| Contractor identity | Yes | Yes | Yes | Yes | Partial | No | Model/service/storage and storage-summary visibility exist; CSLB live verification and action CLIs remain pending. |
| Decision record | Yes | Yes | Yes | Yes | Partial | No | Pre-permit decision model/service/storage and storage-summary visibility exist; agenda/staff-report adapters remain pending. |
| Opportunity enrichment | Yes | Yes | Yes | Yes | Partial | No | Cross-layer scoring uses a versioned default profile, persisted reports, and storage-summary visibility. |
| Lead review package | Yes | Yes | Yes | Yes | Partial | No | Review gate, dedicated storage, and storage-summary visibility exist after enrichment. |
| Lead dedupe | Yes | Yes | Yes | Yes | Partial | No | Code/tests/docs, cross-run fingerprint/result storage, and storage-summary visibility exist. |
| Lead workflow status | Yes | Yes | Yes | Yes | Partial | No | Status/event model, docs, storage, storage-summary visibility, and matrix-constrained status rules exist. |
| Result ledger/share calculation | Yes | Yes | Yes | Yes | Partial | No | Ledger/share model now has explicit share states for pending gross value, pending share rate, calculated share, and not-applicable outcomes. |
| Outreach preview | No | No | No | No | No | No | Planned only; no external action should be implied. |
| UI/operator app | No | No | No | No | No | No | Planned only. |

## Defect ledger

| ID | Severity | Layer | File(s) | Observed fact | Why it matters | Root cause | Recommended fix | Disposition |
|---|---|---|---|---|---|---|---|---|
| CS-VIAM-001 | P1 | Doctrine | `README.md` | README previously lagged the newer post-parcel layers. | Runtime and doctrine drift apart. | Rapid implementation outpaced docs. | Keep README linked to the canonical implementation-status matrix and audit inventory. | Fixed; monitor forward. |
| CS-VIAM-002 | P1 | Persistence | `src/constructionsight/storage/*` | Movement/identity, post-enrichment lead workflow, parcel core, and site-resolution report layers now have dedicated ORM/store coverage. Optional preview archives and some nested child tables remain intentionally unimplemented. | Remaining gaps are now narrower and should not be confused with missing core persistence. | Architecture-first implementation sequence. | Add optional archives or child tables only when query requirements justify them. | Partially fixed; narrow remaining backlog. |
| CS-VIAM-003 | P1 | Source maturity | `source_status_report.py`, `source_status_cli.py`, `data/source_registry.seed.json` | Seed, partial, contract-ready, live-read-only, and production-ready source states are now reported separately. | Product must not overclaim source readiness. | Source records and adapter contracts previously had separate audits but no combined status report. | Keep source status reporting aligned with source verification and adapter maturity. | Fixed; monitor forward. |
| CS-VIAM-004 | P1 | Adapter maturity | `src/constructionsight/adapters/specs.py` | Most adapter families are placeholders; CEQAnet is contract-ready, not live production coverage. | Avoid false live-integration claims. | Adapter contracts preceded live adapters. | Use source-status report before making coverage claims. | Partially fixed; live maturity still backlog. |
| CS-VIAM-005 | P1 | Geometry | `parcel_geometry.py`, `parcel_site_resolution.py` | Geometry parsing now removes simple closing-ring duplication, supports GeoJSON Feature payloads, preserves polygon centroid approximation limits, and propagates envelope-only containment limits into parcel-backed site candidates. | Prevents geometry-derived candidates from being overstated as survey-grade boundary proof. | Dependency-light first implementation. | Add topology-grade point-in-polygon and projection-aware calculations later. | Partially fixed; topology still backlog. |
| CS-VIAM-006 | P1 | Scoring | `opportunity_enrichment_service.py`, `opportunity_scoring_profile.py` | Opportunity enrichment now uses a versioned default scoring profile and records profile key/version in reports. | Future tuning can preserve old report semantics instead of silently changing score meaning. | First-pass scoring implementation was hardcoded. | Add additional profile versions only with explicit doctrine and tests. | Fixed; monitor forward. |
| CS-VIAM-007 | P1 | Workflow | `lead_workflow_service.py`, `lead_workflow_rules.py` | Lead workflow status moves are constrained by a transition matrix and final statuses have no outgoing moves. | Prevents invalid operational state jumps while preserving append-only event history. | Initial workflow model prioritized audit events. | Add any future override/reopen behavior only with explicit doctrine and tests. | Fixed; monitor forward. |
| CS-VIAM-008 | P1 | Result ledger | `result_ledger_models.py`, `result_ledger_service.py` | Won results can now explicitly distinguish pending gross value, pending share rate, and calculated share. | Pending-share uncertainty is queryable and no longer hidden only in limitation text. | Share-rate uncertainty was preserved but not structurally represented. | Add future business-specific enforcement only after explicit review. | Fixed; monitor forward. |
| CS-VIAM-009 | P2 | CLI | `pyproject.toml` | Persisted layers now have a storage-summary CLI and source-status CLI, but dedicated action/list/detail CLIs are still pending. | Operators can verify storage shape/counts and source maturity, but cannot yet operate every persisted domain layer directly. | Model/service/storage-first implementation. | Add consolidated lead/parcel operator CLIs after transition and source maturity rules are hardened. | Partially fixed. |
| CS-VIAM-010 | P2 | Documentation | `docs/architecture/*` | Lead dedupe, workflow, result ledger, and source-status docs now exist or are represented in the status matrix. | Status matrix must not remain stale after documentation lands. | Rapid implementation outpaced matrix reconciliation. | Keep status matrix synchronized with documentation/runtime. | Fixed. |

## Forward cleanup rule

Every future feature PR must update this matrix or explicitly state why no status changed. A new model or service must not silently bypass documentation, tests, persistence review, CLI review, and limitation/provenance review.

See `docs/audits/full_repo_audit_inventory.md` for the canonical full-repo audit inventory.
