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
| Source registry | Yes | Yes | Yes | Yes | Yes | No | Seed sources remain unverified until checked. |
| Adapter contracts | Yes | Yes | Yes | N/A | Yes | No | Most adapter families remain placeholder contracts. CEQAnet is contract-ready, not live. |
| Universal intake | Yes | Yes | Yes | Partial | Yes | No | Source-neutral records and routing exist; live source breadth is limited. |
| Opportunity transition intake | Yes | Yes | Yes | Partial | Yes | No | Converts intake facts into opportunity candidates. |
| Shovels/Regrid gap alignment | Yes | Yes | Yes | N/A | Yes | No | Planning and gap matrix exists; not a claim of platform parity. |
| Parcel/site resolution | Yes | Yes | Yes | Partial | Yes | No | Hint-based resolution exists with confidence and limitations. |
| Parcel source registry | Yes | Yes | Yes | No | Yes | No | Tracks source targets; does not import live parcel coverage. |
| Parcel schema preview | Yes | Yes | Yes | No | Yes | No | Pre-import schema gate exists. |
| Parcel row preview | Yes | Yes | Yes | No | Yes | No | Pre-record row gate exists. |
| Parcel core record | Yes | Yes | Yes | No | No | No | Canonical parcel model exists; ORM/store coverage is pending. |
| Geometry normalization | Yes | Yes | Yes | No | No | No | First-pass WKT/GeoJSON summary exists; polygon-grade topology is pending. |
| Parcel-backed site resolution | Yes | Yes | Yes | No | No | No | Matches site hints to parcel records; envelope-only containment can overmatch. |
| Permit snapshot transition spine | Yes | Yes | Yes | Yes | No | No | Source-neutral permit movement model and movement storage exist; recurring live adapters and operator commands remain pending. |
| Contractor identity | Yes | Yes | Yes | Yes | No | No | Model/service and dedicated storage exist; CSLB live verification and operator commands remain pending. |
| Decision record | Yes | Yes | Yes | Yes | No | No | Pre-permit decision model/service and dedicated storage exist; agenda/staff-report adapters and operator commands remain pending. |
| Opportunity enrichment | Yes | Yes | Yes | No | No | No | Cross-layer scoring exists; weights are currently hardcoded. |
| Lead review package | Yes | Yes | Yes | No | No | No | Review gate exists after enrichment. |
| Lead dedupe | Yes | Yes | Yes | No | No | No | Code/tests/docs exist; cross-run dedupe persistence remains pending. |
| Lead workflow status | Yes | Yes | Yes | No | No | No | Status/event model and docs exist; transition matrix hardening and persistence remain pending. |
| Result ledger/share calculation | Yes | Yes | Yes | No | No | No | Ledger/share model and docs exist; business semantics for pending share and persistence remain pending. |
| Outreach preview | No | No | No | No | No | No | Planned only; no external action should be implied. |
| UI/operator app | No | No | No | No | No | No | Planned only. |

## Defect ledger

| ID | Severity | Layer | File(s) | Observed fact | Why it matters | Root cause | Recommended fix | Disposition |
|---|---|---|---|---|---|---|---|---|
| CS-VIAM-001 | P1 | Doctrine | `README.md` | README previously lagged the newer post-parcel layers. | Runtime and doctrine drift apart. | Rapid implementation outpaced docs. | Keep README linked to the canonical implementation-status matrix and audit inventory. | Fixed; monitor forward. |
| CS-VIAM-002 | P1 | Persistence | `src/constructionsight/storage/*` | Movement/identity layers now have dedicated ORM/store coverage, but parcel core, geometry, site-resolution reports, opportunity enrichment, lead review, dedupe, workflow, and result ledger layers are not fully represented in ORM/store coverage. | Remaining model/service layers cannot all be operationally stored or queried across runs. | Architecture-first implementation sequence. | Continue persistence batches without lossy projection; preserve full payloads, reasons, confidence, and limitations. | Partially fixed; remaining backlog. |
| CS-VIAM-003 | P1 | Source maturity | `data/source_registry.seed.json` | Seed sources are marked `unverified`. | Product must not overclaim source readiness. | Source hardening is not complete. | Preserve unverified status and document meaning. | Fix docs now; verify later. |
| CS-VIAM-004 | P1 | Adapter maturity | `src/constructionsight/adapters/specs.py` | Most adapter families are placeholders; CEQAnet is contract-ready, not live production coverage. | Avoid false live-integration claims. | Adapter contracts preceded live adapters. | Add maturity language to README/status/audit docs. | Fix docs now. |
| CS-VIAM-005 | P1 | Geometry | `parcel_geometry.py`, `parcel_site_resolution.py` | Centroid is first-pass coordinate average; site containment uses envelope checks. | Can produce spatial false positives. | Dependency-light first implementation. | Add geometry hardening PR with topology limitations and tests. | Backlog Phase 6. |
| CS-VIAM-006 | P1 | Scoring | `opportunity_enrichment_service.py` | Weights are hardcoded in service logic. | Scores are deterministic but not profile-versioned. | First-pass scoring implementation. | Add versioned scoring profile. | Backlog Phase 7. |
| CS-VIAM-007 | P1 | Workflow | `lead_workflow_service.py` | Status transitions are append-only and not matrix-constrained. | Invalid operational state jumps remain possible. | Initial workflow model prioritized audit events. | Add transition matrix and closed-state rules. | Backlog. |
| CS-VIAM-008 | P1 | Result ledger | `result_ledger_models.py`, `result_ledger_service.py` | Won result can carry gross value without share when share rate is missing, as a limitation. | May be acceptable as pending-share, but business semantics are not explicit. | Share-rate uncertainty not yet governed. | Add explicit pending-share doctrine/status or enforce share requirement. | Backlog/business review. |
| CS-VIAM-009 | P2 | CLI | `pyproject.toml` | New lead workflow/result layers do not have CLI commands. | Operators cannot use them without Python. | Model/service-first implementation. | Add consolidated lead CLI after persistence plan. | Backlog Phase 5. |
| CS-VIAM-010 | P2 | Documentation | `docs/architecture/*` | Lead dedupe, workflow, and result ledger docs now exist. | Status matrix must not remain stale after documentation lands. | Rapid implementation outpaced matrix reconciliation. | Keep status matrix synchronized with documentation/runtime. | Fixed in this PR. |

## Forward cleanup rule

Every future feature PR must update this matrix or explicitly state why no status changed. A new model or service must not silently bypass documentation, tests, persistence review, CLI review, and limitation/provenance review.

See `docs/audits/full_repo_audit_inventory.md` for the canonical full-repo audit inventory.
