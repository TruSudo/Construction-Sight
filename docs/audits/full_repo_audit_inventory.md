# Full-Repo Audit Inventory

This audit reconciles the current ConstructionSight repository state after movement/identity persistence, post-enrichment lead workflow persistence, parcel/site persistence, geometry hardening, versioned scoring-profile work, lead workflow status-rule hardening, result-ledger share-state hardening, layered source-status/readiness/audit/checklist/planning work, and controlled source-registry apply governance.

## Executive status

ConstructionSight now has a substantial tested model/service architecture for lawful public-record construction intelligence. The strongest implemented areas are source-neutral records, CEQAnet guarded operator tooling, parcel/site reasoning, parcel core records, parcel-backed site resolution, permit movement modeling, contractor identity normalization, decision records, versioned opportunity enrichment, lead review, dedupe, matrix-constrained workflow status, result ledger/share-state modeling, layered source-governance reporting and planning, controlled registry-status apply, storage-summary reporting, and dedicated persistence for movement/identity, parcel/site, and post-enrichment workflow records.

This is not yet a production live-source platform. Live source coverage remains limited. Most adapter families remain contract-ready or placeholder contracts, not verified recurring integrations. CEQAnet has guarded operator/archive tooling and live-execution-adjacent commands, but it must not be described as production-grade recurring coverage unless later source-maturity work proves that status. Controlled registry apply changes only an approved verification-status field and does not itself establish live coverage.

No external outreach-sending behavior is implemented or implied. The GUI/operator application remains planned.

## Status labels

| Label | Meaning |
|---|---|
| Implemented | Runtime model, service, CLI, or audit logic exists in `src/constructionsight`. |
| Tested | Dedicated test coverage exists in `tests`. |
| Documented | Architecture, doctrine, matrix, or README documentation exists. |
| Persisted | SQLAlchemy ORM/store coverage exists or the layer is deliberately fixture/config-backed. |
| CLI/operator access | A script or Typer command exposes the function to an operator. |
| Live source integrated | The code performs lawful live source execution and is documented/tested as such. |
| Planned | Identified but not implemented. |

## Pipeline inventory

| Layer | Primary files | Implemented | Tested | Documented | Persisted | CLI/operator access | Live source integrated | Known limitations | Required next cleanup |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| Lawful intake boundary | `access_policy.py`, intake modules, adapter contracts | Yes | Yes | Yes | Partial | Yes | No | Boundary is enforced at contract/tooling level; source breadth remains limited. | Preserve lawful boundary in every new source PR. |
| Source registry | `source_registry.py`, `source_registry_store.py`, `source_status_report.py`, `source_readiness_*`, `source_verification_*`, `source_registry_update_plan_*`, `source_registry_apply_*`, `data/source_registry.seed.json` | Yes | Yes | Yes | Yes/file-backed | Yes | No | Current seed records remain unverified; controlled apply can change only an approved evidence-backed verification status. | Perform source-specific manual verification before any actual status promotion. |
| Source readiness workflow | `source_readiness_models.py`, `source_readiness_service.py`, `source_readiness_cli.py` | Yes | Yes | Yes | No | Yes | No | Report-only workflow; does not mutate source verification status or claim live coverage. | Preserve non-mutating readiness evidence. |
| Audit package | `source_verification_evidence_models.py`, `source_verification_evidence_service.py`, `audit_package_cli.py`, `docs/architecture/audit_package.md` | Yes | Yes | Yes | No | Yes | No | Report-only package; preserves redirect/final URL evidence but does not replace manual verification or create source coverage. | Use with checklist evidence before planning a status change. |
| Source verification checklist | `source_verification_checklist_*` | Yes | Yes | Yes | No | Yes | No | Operator observations remain file/report-backed and require evidence references for apply. | Complete source-specific observations with reproducible evidence. |
| Source promotion and registry planning | `source_promotion_plan_*`, `source_registry_update_plan_*` | Yes | Yes | Yes | No | Yes | No | Planning is dry-run-first and may propose only registry verification-status payloads. | Review plan reasons, limitations, evidence, and digest before apply. |
| Controlled source registry apply | `source_registry_apply_models.py`, `source_registry_apply_service.py`, `source_registry_update_plan_cli.py` | Yes | Yes | Yes | File-backed | Yes | No | Requires exact plan digest, current-state match, evidence references, status-only mutation, explicit `--apply`, audit output, and atomic file replacement. Verified-source downgrade is intentionally excluded. | Add separate revocation doctrine only if verified-source downgrade becomes necessary. |
| Adapter contracts | `adapters/specs.py`, `adapters/registry.py`, `source_status_report.py` | Yes | Yes | Yes | N/A | Yes | No | Contracts are not equivalent to live integrations. | Add live maturity only after verified source workflows exist. |
| CEQAnet fixture/query/listing/detail/operator/archive tooling | `ceqanet_*` modules and CLIs | Yes | Yes | Yes | Partial | Yes | Limited/guarded | Production recurring coverage is not established and the seed source remains unverified. | Complete source verification and recurring-run governance. |
| Universal intake | `intake_models.py`, `intake_service.py`, `intake_cli.py` | Yes | Yes | Yes | Partial | Yes | No | Routes unknown/unmapped fields but does not imply all formats are covered. | Expand fixture coverage before broader source claims. |
| Opportunity transition intake | `opportunity_models.py`, `opportunity_service.py`, `opportunity_cli.py` | Yes | Yes | Yes | Partial | Yes | No | Converts source-neutral facts into candidates; not an outreach system. | Persist candidate runs if used operationally. |
| External intelligence capability spine | `external_intelligence_*` | Yes | Yes | Yes | N/A | Yes | No | Capability modeling only; not Shovels parity. | Keep as gap/maturity analysis, not runtime parity claim. |
| Shovels/Regrid gap alignment | `external_gap_*`, `docs/architecture/shovels_regrid_gap_alignment.md` | Yes | Yes | Yes | N/A | Yes | No | Capability targets only. | Continue separating capability target from implementation truth. |
| Parcel source registry | `parcel_source_*` | Yes | Yes | Yes | Config/fixture-backed | Yes | No | Tracks source targets, not verified imports. | Add source verification and import-readiness gate. |
| Parcel schema preview | `parcel_schema_*`, `parcel_source_cli.py` | Yes | Yes | Yes | No | Yes | No | Preview reports are ephemeral unless persisted later. | Store reports only if operator audit requires replay. |
| Parcel row preview | `parcel_row_preview*`, `parcel_source_cli.py` | Yes | Yes | Yes | No | Yes | No | Preview only; does not create canonical records by itself. | Add persisted import batch audit if live parcel ingestion begins. |
| Parcel core record | `parcel_core_models.py`, `parcel_record_builder.py`, `storage/parcel_site_*` | Yes | Yes | Yes | Yes | No | No | Canonical model and storage exist; live import workflow remains pending. | Add verified import workflow when source maturity permits. |
| Geometry normalization | `parcel_geometry.py`, `storage/parcel_site_*` | Yes | Yes | Yes | Payload | No | No | Geometry parsing is hardened, but still not survey-grade topology. | Add topology-grade containment and projection-aware calculations later. |
| Parcel-backed site resolution | `parcel_site_resolution.py`, `storage/parcel_site_*` | Yes | Yes | Yes | Yes | No | No | Envelope containment can overmatch; geometry limitations are propagated. | Add topology-grade containment and operator replay flow. |
| Permit snapshot transition spine | `permit_transition_models.py`, `permit_transition_service.py`, `storage/movement_identity_*` | Yes | Yes | Yes | Yes | No | No | Persisted movement records exist, but no recurring live adapter workflow is proven. | Add operator workflow and recurring run storage governance. |
| Contractor identity | `contractor_identity_*`, `storage/movement_identity_*` | Yes | Yes | Yes | Yes | No | No | Conservative normalization only; CSLB live verification remains pending. | Add verification adapter and CLI after lawful source maturity review. |
| Decision records | `decision_record_*`, `storage/movement_identity_*` | Yes | Yes | Yes | Yes | No | No | Model/service/storage exist; agenda/staff-report adapters remain pending. | Add source adapters and relationship mapping. |
| Opportunity enrichment | `opportunity_enrichment_*`, `opportunity_scoring_profile.py`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Default scoring profile is versioned; future profile changes need explicit tests/doctrine. | Add operator CLI. |
| Lead review package | `lead_review_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Review package exists and is persisted; operator CLI is pending. | Add operator CLI. |
| Lead dedupe | `lead_dedupe_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Cross-run dedupe storage exists; operator CLI is pending. | Add lead/operator CLI. |
| Lead workflow status | `lead_workflow_*`, `lead_workflow_rules.py`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Status moves are matrix-constrained; final statuses have no outgoing moves. | Add explicit override/reopen only if business doctrine later requires it. |
| Result ledger/share calculation | `result_ledger_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Share state is explicit and persisted; business-specific enforcement may still evolve later. | Add business-specific share enforcement only after explicit review. |
| Storage/database initialization | `storage/database.py`, `storage/*_orm.py`, `storage/*_store.py` | Yes | Yes | Yes | Partial | Yes | No | Core model records are covered; optional preview archives and child tables remain. | Continue persistence only when query or replay needs require it. |
| CLI script registration | `pyproject.toml`, CLI modules | Yes | Yes | Yes | N/A | Partial | No | Layered source governance and storage-summary CLIs exist; many persisted workflow layers still lack action/list/detail commands. | Add consolidated lead/operator CLI. |
| CI quality gate | `.github/workflows/ci.yml` | Yes | N/A | Yes | N/A | N/A | N/A | Local Python 3.12 passing does not prove 3.11 unless CI also passes. | Keep 3.11/3.12 matrix green. |
| Adapter/source coverage audits | audit modules, source-governance services, CLI audit commands | Yes | Yes | Yes | N/A | Yes | No | Source count is small and seed-based; layered governance prevents seed records from being overclaimed. | Verify sources individually before coverage claims. |

## Current observed source-audit outcome

An HTTP audit-package run against `data/source_registry.seed.json` produced this report-only review state:

| Source | Redirect classification | Recommendation |
|---|---|---|
| CEQAnet State Clearinghouse | `cross_host_redirect` | `keep_unverified_reachable` |
| CSLB Public License Search | `no_redirect` | `keep_unverified_reachable` |
| San Bernardino County EZOP | `same_host_redirect` | `keep_unverified_reachable` |
| Riverside County PLUS Online | `downgraded_to_http` | `keep_unverified_reachable` |

All four URLs were reachable in that run, but all four source records remain unverified. The audit package does not replace manual verification. The controlled apply layer added after this observation does not itself promote any current source.

## Contradiction ledger

| ID | Severity | File(s) | Observed contradiction | Runtime truth | Required fix | Disposition |
|---|---|---|---|---|---|---|
| CS-AUDIT-001 | P1 | status/storage docs | Earlier status marked movement/identity persistence as missing. | Movement/identity records have dedicated ORM/store coverage with payload JSON preservation. | Mark persistence accurately while keeping CLI and live integration absent. | Fixed. |
| CS-AUDIT-002 | P2 | status/architecture docs | Lead dedupe, lead workflow, and result ledger documentation status was stale. | Dedicated docs exist. | Mark documentation accurately without claiming CLI. | Fixed. |
| CS-AUDIT-003 | P2 | `README.md` | Broad limitation language implied no newer ORM coverage. | Movement/identity, parcel/site, and post-enrichment workflow records are persisted. | Narrow limitation language. | Fixed. |
| CS-AUDIT-004 | P1 | storage matrix/runtime | Batch 2 lead workflow records were listed as pending storage. | Dedicated ORM/store coverage exists. | Reconcile docs. | Fixed. |
| CS-AUDIT-005 | P1 | storage matrix/runtime | Parcel core and site-resolution reports were listed as pending storage. | Dedicated storage exists. | Reconcile docs. | Fixed. |
| CS-AUDIT-006 | P1 | enrichment service/docs | Scoring weights were hardcoded and not profile-versioned. | Versioned profile and persisted profile identity exist. | Reconcile docs. | Fixed. |
| CS-AUDIT-007 | P1 | workflow service/rules/docs | Workflow transitions were append-only without matrix enforcement. | Transition matrix and final-state immutability exist. | Reconcile docs. | Fixed. |
| CS-AUDIT-008 | P1 | result ledger service/storage/docs | Won-result share uncertainty was limitation text only. | Explicit share states exist and persist. | Reconcile docs. | Fixed. |
| CS-AUDIT-009 | P1 | source status CLI/docs | Seed records and adapter contracts could be conflated with verified usable sources. | Source-status reporting separates source and adapter maturity. | Reconcile maturity language. | Fixed. |
| CS-AUDIT-010 | P2 | source status CLI/tests | CLI root behavior conflicted with documented `report` usage. | Tested `report` subcommand exists. | Align tests and docs. | Fixed. |
| CS-AUDIT-011 | P1 | source readiness modules/docs | Readiness evidence lacked a dedicated report-only workflow. | Conservative report-only readiness exists. | Preserve non-mutating behavior. | Fixed. |
| CS-AUDIT-012 | P1 | audit package modules/docs | Audit-package operator surface was absent from canonical docs. | Report-only URL/HTTP/redirect evidence exists. | Reconcile docs. | Fixed. |
| CS-AUDIT-013 | P1 | source plan/apply modules/docs | Registry planning previously ended with proposed payloads but no explicit safe apply boundary. | Apply now requires an exact reviewed digest, unchanged source payload, evidence references, action/status agreement, status-only mutation, explicit authorization, audit output, and atomic replacement. | Reconcile README, status matrix, audit inventory, and architecture contract without promoting current sources. | Fixed in this PR. |

## Persistence coverage ledger

| Layer | Persistence truth | Notes |
|---|---|---|
| Domain records | Persisted | First-generation domain ORM/store exists. |
| Intelligence records | Persisted | First-generation intelligence ORM/store exists. |
| Source registry | Persisted/config-backed | Seed/config source records and store support exist; file-backed controlled apply is available. |
| Source readiness reports | Not persisted | JSON-safe report output; persistence only if audit replay requires it. |
| Audit packages | Not persisted | JSON-safe report output; persistence only if audit replay requires it. |
| Checklist/promotion/update plans | Not dedicated ORM | File/report-backed evidence and plans. |
| Source apply reports | Not dedicated ORM | Required JSON audit output contains plan and registry digests plus row-level evidence. |
| Parcel source/schema/row preview | Not dedicated ORM | Preview layers are generally ephemeral unless operator audit requires storage. |
| Parcel core records | Persisted | Indexed fields plus full JSON payload. |
| Parcel geometry summaries | Payload/indexed parent fields | Not survey-grade topology. |
| Parcel-backed site-resolution reports | Persisted | Indexed result fields plus full JSON payload. |
| Permit snapshots | Persisted | Indexed fields plus full payload JSON. |
| Permit transitions | Persisted | Indexed fields plus full payload JSON. |
| Contractor identities | Persisted | Indexed fields plus full payload JSON. |
| Decision records | Persisted | Indexed fields plus full payload JSON. |
| Opportunity enrichment reports | Persisted | Indexed score/confidence/profile fields plus full payload JSON. |
| Lead review packages | Persisted | Indexed review fields plus full payload JSON. |
| Lead fingerprints / duplicate results | Persisted | Indexed dedupe fields plus full payload JSON. |
| Lead workflows / workflow events | Persisted | Indexed status/event fields plus full payload JSON. |
| Result ledgers / share records | Persisted | Indexed outcome/share-state fields plus full payload JSON and calculated share rows. |

Persistence rule: generic domain tables are not equivalent to newer source-neutral models unless the mapping is deliberate, lossless, and preserves full payloads, reasons, confidence, limitations, provenance, and future fields.

## CLI/operator exposure ledger

| CLI/script area | Runtime exposure | Notes |
|---|---|---|
| Core CLI | Present | Main `constructionsight` command exposes audit/list/graph and related commands. |
| Intake CLI | Present | Universal intake has operator access. |
| Opportunity intake CLI | Present | Opportunity candidate conversion has operator access. |
| External intelligence/gap CLI | Present | Capability/gap reporting has operator access. |
| Parcel source/schema/row preview CLI | Present | Parcel pre-import preview tooling exists. |
| Site resolution CLI | Present | Site-resolution preview tooling exists. |
| Storage summary CLI | Present | Reports ORM table existence and row counts. |
| Source status/readiness/audit CLI | Present | Non-mutating source maturity evidence is exposed. |
| Source checklist/promotion/plan CLI | Present | Manual observation and dry-run planning surfaces exist. |
| Source controlled apply CLI | Present | `constructionsight-source-plan apply` enforces digest approval, evidence, status-only mutation, audit output, and atomic replacement. |
| CEQAnet CLIs | Present | Fixture, listing, detail, enrichment, chain, persistence, operator, export, archive, and verify commands exist. |
| Permit transition CLI | Absent | Model/service/storage exist but operator CLI is pending. |
| Contractor identity CLI | Absent | Model/service/storage exist but operator CLI is pending. |
| Decision record CLI | Absent | Model/service/storage exist but operator CLI is pending. |
| Opportunity enrichment CLI | Absent | Model/service/storage exists; no dedicated operator command. |
| Lead review/dedupe/workflow/result CLI | Absent | Model/service/storage exists; operator commands pending. |
| Parcel core / site-resolution persistence CLI | Absent | Model/service/storage exists; operator commands pending. |
| Outreach sending CLI | Absent | No external outreach-sending behavior is implemented or implied. |
| GUI/operator app | Absent | Planned only. |

## Source maturity ledger

| Maturity stage | ConstructionSight status |
|---|---|
| Seed source | Four seed-only records remain in `data/source_registry.seed.json`. |
| Source-readiness evidence | Report-only workflow exists. |
| Audit-package evidence | Report-only workflow exists. |
| Manual checklist evidence | Observation template and checklist workflow exist. |
| Promotion/update plan | Dry-run plan and deterministic approval digest exist. |
| Controlled registry apply | Evidence-gated status-only file apply exists; no current source is promoted by implementation alone. |
| Verified usable source | Current source-status report shows zero verified usable sources. |
| Contract-ready adapter | Exists for registered families, including CEQAnet; not a live coverage claim. |
| Live read-only integration | Limited/guarded. |
| Production-grade recurring integration | Not established. |
| Operator workflow | Partial for source governance, CEQAnet, preview/audit commands, and storage summary; lead workflow operator app/CLI remains pending. |

## Limitation and uncertainty preservation check

Current architecture must preserve the following fields or concepts wherever applicable:

- reasons
- limitations
- confidence scores or confidence bands
- source keys and source record IDs
- payload JSON or full normalized payloads
- provenance and evidence references
- lawful-access boundaries
- review-needed states
- unknown/unmapped fields
- workflow status-transition history
- result share-state uncertainty
- source verification and adapter maturity state
- source-readiness reachability evidence and next action
- audit-package original/final URL, HTTP, redirect, recommendation, and next-action evidence
- source plan action, original/proposed payload, evidence references, and approval digest
- source apply original/updated registry digests and row-level audit outcome

These fields are not cleanup noise. They are audit and evidentiary controls. Future PRs must not delete, narrow, or flatten them merely to simplify models, storage, CLI output, or tests.

## Forward cleanup enforcement

Every future feature PR must either update the implementation-status matrix or explicitly state why no status changed.

Every new model or service must be reviewed for:

- tests
- documentation
- persistence need
- CLI/operator need
- lawful-access boundary
- reasons/confidence/limitations preservation
- doctrine/runtime impact

No future PR should merge while it knowingly introduces doctrine/runtime drift, stale maturity claims, missing limitations, broken quality gates, or unreviewed persistence/CLI implications.
