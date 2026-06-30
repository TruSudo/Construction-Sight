# Full-Repo Audit Inventory

This audit reconciles the current ConstructionSight repository state after movement/identity persistence, post-enrichment lead workflow persistence, and parcel/site persistence work.

## Executive status

ConstructionSight now has a substantial tested model/service architecture for lawful public-record construction intelligence. The strongest implemented areas are source-neutral records, CEQAnet guarded operator tooling, parcel/site reasoning, parcel core records, parcel-backed site resolution, permit movement modeling, contractor identity normalization, decision records, opportunity enrichment, lead review, dedupe, workflow status, result ledger modeling, and dedicated persistence for movement/identity, parcel/site, and post-enrichment workflow records.

This is not yet a production live-source platform. Live source coverage remains limited. Most adapter families remain contract-ready or placeholder contracts, not verified recurring integrations. CEQAnet has guarded operator/archive tooling and live-execution-adjacent commands, but it must not be described as production-grade recurring coverage unless later source-maturity work proves that status.

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
| Source registry | `source_registry.py`, `source_registry_store.py`, `data/source_registry.seed.json` | Yes | Yes | Yes | Yes | Yes | No | Seed records remain unverified until checked. | Add source verification workflow before claiming coverage. |
| Adapter contracts | `adapters/specs.py`, `adapters/registry.py` | Yes | Yes | Yes | N/A | Yes | No | Contracts are not equivalent to live integrations. | Add maturity status per adapter family. |
| CEQAnet fixture/query/listing/detail/operator/archive tooling | `ceqanet_*` modules and CLIs | Yes | Yes | Yes | Partial | Yes | Limited/guarded | Operator/archive tooling exists, but production recurring coverage is not established. | Add source-maturity report and recurring-run governance. |
| Universal intake | `intake_models.py`, `intake_service.py`, `intake_cli.py` | Yes | Yes | Yes | Partial | Yes | No | Routes unknown/unmapped fields but does not imply all formats are covered. | Expand fixture coverage before broader source claims. |
| Opportunity transition intake | `opportunity_models.py`, `opportunity_service.py`, `opportunity_cli.py` | Yes | Yes | Yes | Partial | Yes | No | Converts source-neutral facts into candidates; not an outreach system. | Persist candidate runs if used operationally. |
| External intelligence capability spine | `external_intelligence_*` | Yes | Yes | Yes | N/A | Yes | No | Capability modeling only; not Shovels parity. | Keep as gap/maturity analysis, not runtime parity claim. |
| Shovels/Regrid gap alignment | `external_gap_*`, `docs/architecture/shovels_regrid_gap_alignment.md` | Yes | Yes | Yes | N/A | Yes | No | Capability targets only. | Continue separating capability target from implementation truth. |
| Parcel source registry | `parcel_source_*` | Yes | Yes | Yes | Config/fixture-backed | Yes | No | Tracks targets, not verified imports. | Add source verification and import-readiness gate. |
| Parcel schema preview | `parcel_schema_*`, `parcel_source_cli.py` | Yes | Yes | Yes | No | Yes | No | Preview reports are ephemeral unless persisted later. | Store reports only if operator audit requires replay. |
| Parcel row preview | `parcel_row_preview*`, `parcel_source_cli.py` | Yes | Yes | Yes | No | Yes | No | Preview only; does not create canonical records by itself. | Add persisted import batch audit if live parcel ingestion begins. |
| Parcel core record | `parcel_core_models.py`, `parcel_record_builder.py`, `storage/parcel_site_*` | Yes | Yes | Yes | Yes | No | No | Canonical model and storage exist; live import workflow remains pending. | Add verified import workflow when source maturity permits. |
| Geometry normalization | `parcel_geometry.py`, `storage/parcel_site_*` | Yes | Yes | Yes | Payload | No | No | First-pass geometry summaries are stored but not survey-grade topology. | Add robust geometry/topology library or stricter limitation checks. |
| Parcel-backed site resolution | `parcel_site_resolution.py`, `storage/parcel_site_*` | Yes | Yes | Yes | Yes | No | No | Envelope containment can overmatch; ambiguity must be preserved. | Add topology-grade containment and operator replay flow. |
| Permit snapshot transition spine | `permit_transition_models.py`, `permit_transition_service.py`, `storage/movement_identity_*` | Yes | Yes | Yes | Yes | No | No | Persisted movement records exist, but no recurring live adapter workflow is proven. | Add operator workflow and recurring run storage governance. |
| Contractor identity | `contractor_identity_*`, `storage/movement_identity_*` | Yes | Yes | Yes | Yes | No | No | Conservative normalization only; CSLB live verification remains pending. | Add verification adapter and CLI only after lawful source maturity review. |
| Decision records | `decision_record_*`, `storage/movement_identity_*` | Yes | Yes | Yes | Yes | No | No | Model/service/storage exist; agenda/staff-report adapters remain pending. | Add source adapters and relationship mapping. |
| Opportunity enrichment | `opportunity_enrichment_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Scores are deterministic but hardcoded, not profile-versioned. | Add versioned scoring profile. |
| Lead review package | `lead_review_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Review package exists and is persisted; operator CLI is pending. | Add operator CLI after workflow semantics are hardened. |
| Lead dedupe | `lead_dedupe_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Cross-run dedupe storage exists; operator CLI is pending. | Add lead/operator CLI. |
| Lead workflow status | `lead_workflow_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Events append; full transition matrix is not enforced. | Add matrix-constrained workflow rules. |
| Result ledger/share calculation | `result_ledger_*`, `storage/lead_workflow_*` | Yes | Yes | Yes | Yes | No | No | Business semantics for won results with missing share rate need review. | Add pending-share doctrine or enforcement. |
| Storage/database initialization | `storage/database.py`, `storage/*_orm.py`, `storage/*_store.py` | Yes | Yes | Yes | Partial | N/A | No | Core model records are covered; optional preview archives and child tables remain. | Continue persistence only when query or replay needs require it. |
| CLI script registration | `pyproject.toml`, CLI modules | Yes | Yes | Yes | N/A | Partial | No | Many persisted workflow layers still lack operator commands. | Add consolidated lead/operator CLI. |
| CI quality gate | `.github/workflows/ci.yml` | Yes | N/A | Yes | N/A | N/A | N/A | Local Python 3.12 passing does not prove 3.11 unless CI also passes. | Keep 3.11/3.12 matrix green. |
| Adapter/source coverage audits | `adapter_audit`, `adapter_coverage`, CLI audit commands | Yes | Yes | Yes | N/A | Yes | No | Source count is small and seed-based. | Add source maturity audit before coverage claims. |

## Contradiction ledger

| ID | Severity | File(s) | Observed contradiction | Runtime truth | Required fix | Disposition in this PR |
|---|---|---|---|---|---|---|
| CS-AUDIT-001 | P1 | `docs/architecture/current_implementation_status.md`, `docs/storage_model_matrix.md` | Earlier status marked movement/identity persistence as missing. | Movement/identity records have dedicated ORM/store coverage with payload JSON preservation. | Mark persistence accurately while keeping CLI and live integration absent. | Fixed. |
| CS-AUDIT-002 | P2 | `docs/architecture/current_implementation_status.md`, architecture docs | Lead dedupe, lead workflow, and result ledger documentation status was stale if marked undocumented. | Dedicated docs exist for lead dedupe, lead workflow status, and result ledger. | Mark documentation accurately without claiming CLI. | Fixed. |
| CS-AUDIT-003 | P2 | `README.md` | Broad limitation language can imply no newer layers have ORM coverage. | Movement/identity, parcel/site, and post-enrichment lead workflow records are persisted. | Narrow limitation language to remaining persistence gaps. | Fixed in this PR. |
| CS-AUDIT-004 | P1 | `docs/storage_model_matrix.md`, runtime storage modules | Batch 2 lead workflow records were listed as pending storage. | Lead workflow records now have dedicated ORM/store coverage. | Update matrix/status/audit/README maturity language. | Fixed. |
| CS-AUDIT-005 | P1 | `docs/storage_model_matrix.md`, runtime storage modules | Parcel core and parcel-backed site-resolution reports were listed as pending storage. | `parcel_core_records` and `site_resolution_results` now have dedicated ORM/store coverage. | Update matrix/status/audit/README maturity language. | Fixed in this PR. |

## Persistence coverage ledger

| Layer | Persistence truth | Notes |
|---|---|---|
| Domain records | Persisted | First-generation domain ORM/store exists. |
| Intelligence records | Persisted | First-generation intelligence ORM/store exists. |
| Source registry | Persisted/config-backed | Seed/config source records and store support exist, but source maturity remains unverified. |
| Parcel source/schema/row preview | Not dedicated ORM | Preview layers are generally ephemeral unless operator audit requires storage. |
| Parcel core records | Persisted | `parcel_core_records` stores indexed parcel and geometry summary fields plus full JSON payload. |
| Parcel geometry summaries | Payload/indexed parent fields | Stored in parcel payload with selected indexed parent columns; not survey-grade topology. |
| Parcel-backed site-resolution reports | Persisted | `site_resolution_results` stores indexed result fields plus full JSON payload. |
| Permit snapshots | Persisted | `permit_snapshots` stores indexed fields plus full payload JSON. |
| Permit transitions | Persisted | `permit_transitions` stores indexed fields plus full payload JSON. |
| Contractor identities | Persisted | `contractor_identities` stores indexed fields plus full payload JSON. |
| Decision records | Persisted | `decision_records` stores indexed fields plus full payload JSON. |
| Opportunity enrichment reports | Persisted | `opportunity_enrichment_reports` stores indexed score/confidence fields plus full payload JSON. |
| Lead review packages | Persisted | `lead_review_packages` stores indexed review fields plus full payload JSON. |
| Lead fingerprints / duplicate results | Persisted | `lead_fingerprints` and `lead_duplicate_results` store indexed dedupe fields plus full payload JSON. |
| Lead workflows / workflow events | Persisted | `lead_workflows` and `lead_workflow_events` store indexed status/event fields plus full payload JSON. |
| Result ledgers / share records | Persisted | `result_ledgers` and `result_share_records` store indexed outcome/share fields plus full payload JSON. |

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
| CEQAnet CLIs | Present | Fixture, listing, detail, enrichment, chain, persistence preview/apply, operator package/report/bundle/export/archive/verify commands exist. |
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
| Seed source | Exists in `data/source_registry.seed.json`; records remain unverified until checked. |
| Verified source | Limited; do not infer broad verification from seed registry presence. |
| Contract-ready adapter | Exists for registered adapter families. |
| Live read-only integration | Limited/guarded; CEQAnet tooling has live-execution-adjacent commands but must not be overclaimed as production recurring coverage. |
| Production-grade recurring integration | Not established. |
| Operator workflow | Partial for CEQAnet and preview/audit commands; lead workflow operator app/CLI remains pending. |

## Limitation and uncertainty preservation check

Current architecture must preserve the following fields or concepts wherever applicable:

- reasons
- limitations
- confidence scores or confidence bands
- source keys
- source record IDs
- payload JSON or full normalized payloads
- provenance/evidence references
- lawful-access boundaries
- review-needed states
- unknown/unmapped fields

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
