# Storage Coverage Matrix

This matrix maps ConstructionSight model/service layers to current SQLAlchemy storage coverage.

## Storage modules verified

Current database initialization imports these ORM modules before `Base.metadata.create_all()`:

- `constructionsight.storage.domain_orm`
- `constructionsight.storage.intelligence_orm`

That means only tables represented in those modules are created by the current database initializer.

## Existing ORM coverage

| Runtime/domain concept | ORM coverage | Notes |
|---|---|---|
| Normalized site/domain records | Yes | `domain_sites` exists. This is not the same as `ParcelCoreRecord`. |
| Normalized named entities | Yes | `domain_entities` exists. This is not the same as `ContractorIdentity`. |
| Normalized permit records | Yes | `domain_permits` exists. This is not the same as `PermitSnapshot`/`PermitTransition`. |
| Normalized planning cases | Yes | `domain_planning_cases` exists. |
| Normalized CEQA records | Yes | `domain_ceqa_records` exists. |
| Normalized agenda items | Yes | `domain_agenda_items` exists. |
| Normalized documents | Yes | `domain_documents` exists. |
| Normalized relationships | Yes | `domain_relationships` exists. |
| First-generation intelligence evidence | Yes | `intelligence_evidence_records` exists. |
| First-generation intelligence entities | Yes | `intelligence_entities` exists. |
| First-generation intelligence relationships | Yes | `intelligence_relationships` exists. |
| First-generation intelligence project clusters | Yes | `intelligence_project_clusters` exists. |
| First-generation intelligence opportunities | Yes | `intelligence_opportunities` exists. |
| Runtime events | Yes | `intelligence_runtime_events` exists. |
| Watchlist items | Yes | `intelligence_watchlist_items` exists. |

## Newer model/service layer storage coverage

| Model/service layer | Model exists | Service exists | Tests exist | ORM/store coverage | Persistence action |
|---|---:|---:|---:|---:|---|
| Parcel source registry | Yes | Yes | Yes | No dedicated ORM | Add only if source registry should become database-backed rather than fixture/config-backed. |
| Parcel schema preview | Yes | Yes | Yes | No | Usually ephemeral; persistence optional. Store reports only if operator audit requires it. |
| Parcel row preview | Yes | Yes | Yes | No | Usually ephemeral; persistence optional. Store reports only if operator audit requires it. |
| ParcelCoreRecord | Yes | Yes | Yes | No dedicated ORM | Add `parcel_core_records` table or map deliberately into `domain_sites` with lossless JSON payload. |
| ParcelGeometry | Yes | Yes | Yes | No dedicated ORM | Store as part of parcel core payload or dedicated geometry table. |
| Parcel-backed site resolution | Yes | Yes | Yes | No | Store resolution reports if used by lead review or audit trails. |
| PermitSnapshot | Yes | Yes | Yes | No dedicated ORM | Add `permit_snapshots`. Required before recurring transition detection is operational. |
| PermitTransition | Yes | Yes | Yes | No dedicated ORM | Add `permit_transitions`. Required for movement history. |
| ContractorIdentity | Yes | Yes | Yes | No dedicated ORM | Add `contractor_identities`; do not collapse into generic `domain_entities` unless lossless payload is retained. |
| ContractorLicense | Yes | Yes | Yes | No dedicated ORM | Store as JSON payload or child table keyed to contractor. |
| DecisionRecord | Yes | Yes | Yes | No dedicated ORM | Add `decision_records`; can relate later to agenda/CEQA/source records. |
| DecisionSiteMatch | Yes | Yes | Yes | No | Store if decision matching feeds review packages. |
| OpportunityEnrichmentReport | Yes | Yes | Yes | No dedicated ORM | Add `opportunity_enrichment_reports`; required for replayable lead scores. |
| OpportunityEnrichmentSignal | Yes | Yes | Yes | No | Store as JSON payload or child table. |
| LeadReviewPackage | Yes | Yes | Yes | No dedicated ORM | Add `lead_review_packages`; required before operator workflow. |
| LeadFingerprint | Yes | Yes | Yes | No dedicated ORM | Add `lead_fingerprints`; required before dedupe can operate across runs. |
| LeadDuplicateResult | Yes | Yes | Yes | No | Store if dedupe decision must be auditable. |
| LeadWorkflowRecord | Yes | Yes | Yes | No dedicated ORM | Add `lead_workflows`; required for operational workflow. |
| LeadWorkflowEvent | Yes | Yes | Yes | No dedicated ORM | Add `lead_workflow_events`; required for state audit trail. |
| ResultLedgerRecord | Yes | Yes | Yes | No dedicated ORM | Add `result_ledgers`; required for business outcome tracking. |
| ResultShareRecord | Yes | Yes | Yes | No dedicated ORM | Add `result_share_records`; required for calculated share audit. |

## Recommended persistence batches

### Batch 1: movement and identity records

Implement first:

- `permit_snapshots`
- `permit_transitions`
- `contractor_identities`
- `decision_records`

Reason: these are source-signal records that later enrichment depends on.

### Batch 2: lead workflow records

Implement second:

- `opportunity_enrichment_reports`
- `lead_review_packages`
- `lead_fingerprints`
- `lead_duplicate_results`
- `lead_workflows`
- `lead_workflow_events`
- `result_ledgers`
- `result_share_records`

Reason: these are operator/workflow records that depend on the movement and identity records.

## Persistence design rule

Do not persist these layers by lossy projection only. If a normalized indexed subset is stored, also preserve a JSON payload with the full model output so reasons, confidence, limitations, and future fields remain auditable.

## Acceptance criteria for persistence PRs

Every new persistent layer must include:

- ORM table with stable ID and useful indexes.
- Store/repository helpers.
- Roundtrip tests from Pydantic model to storage payload and back where feasible.
- Database initialization coverage.
- No weakening of existing tests.
- No claim of live source integration.
