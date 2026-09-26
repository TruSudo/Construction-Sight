# Internal adversarial baseline inventory — 2026-08-21

Baseline commit: `5f101b7bdddfd695904eb02144350e06207d9ded`

This artifact records the complete-tree internal adversarial characterization performed against the exact baseline above before remediation began. It is not an independent review, approval, certification, or defect-closure artifact. The baseline branch `audit/pre-remediation-baseline-2026-08-21` preserves the examined tree.

## Existing active defects receiving additional evidence

The frozen review found additional manifestations of existing root causes. The original active-defect facts remain unchanged.

- `CS-SR-001`, `CS-SR-004`, `CS-SR-006`, `CS-SR-034`: architecture and semantic-certification coverage remains incomplete for alias/member imports, re-exports, effect-bearing parameters, and canonical-gate wiring.
- `CS-SR-014`: mandatory CI-command evidence is checked textually; commented command text can satisfy the repository scanner even though it is not executable workflow structure.
- `CS-SR-017`: adversarial contract coverage proves referenced test paths/categories exist but does not prove a referenced test semantically witnesses the claimed category.
- `CS-SR-020`, `CS-SR-041`: response/resource bounds establish the pre-materialization-bound invariant; analogous local-file, archive, and adapter boundaries are registered separately as `CS-SR-055`.
- `CS-SR-022`: database transactionality provides the precedent for atomic mutation; coupled filesystem artifact publication is a distinct boundary registered as `CS-SR-058`.
- `CS-SR-030`: mutable authorized CEQAnet write-plan TOCTOU provides the precedent for authorization/content binding; general recursive immutability remains distinct as `CS-SR-059`.
- `CS-SR-033`: repository-governance evidence containment is distinct from runtime evidence-root containment, registered separately as `CS-SR-054`.
- `CS-SR-039`, `CS-SR-040`: ambient HTTP authority, injected clients, ArcGIS-local transport, and exact request/evidence authority remain active and unremediated.

## Newly registered root causes

`CS-SR-043` through `CS-SR-059` are new root causes that remain after reconciliation against `CS-SR-001` through `CS-SR-042`:

- `CS-SR-043` — effect implementation authority
- `CS-SR-044` — trusted time authority
- `CS-SR-045` — lawful-access fact authority
- `CS-SR-046` — epistemic provenance authority
- `CS-SR-047` — derived identity integrity
- `CS-SR-048` — operational confidence gating
- `CS-SR-049` — duplicate review gate
- `CS-SR-050` — business transition concurrency
- `CS-SR-051` — historical ledger separation
- `CS-SR-052` — result ledger content identity
- `CS-SR-053` — financial decimal integrity
- `CS-SR-054` — runtime evidence containment
- `CS-SR-055` — pre-materialization resource bounds
- `CS-SR-056` — database schema evolution
- `CS-SR-057` — foundational domain invariants
- `CS-SR-058` — cross-artifact commit atomicity
- `CS-SR-059` — deep content immutability

## Root-cause dependency order

1. Certification/architecture proof must become trustworthy before later green results are treated as meaningful.
2. ConstructionSight must own effect implementation and authoritative time.
3. Lawful-access, provenance, derived identity, and confidence must be evidence-bound.
4. Duplicate and workflow transitions must be blocked by unresolved review state and protected by atomic durable transitions.
5. Historical ledgers, result identity, and financial arithmetic must become replay-safe and exact.
6. Runtime evidence containment, local resource bounds, schema evolution, domain invariants, cross-artifact commit atomicity, and recursive immutability must be enforced.
7. After remediation, the complete tree must be adversarially reviewed again before a successor candidate is frozen.

## Remediation constraints

- Zero-feature invariant: security boundaries add no unrelated capability.
- Semantic-equivalence invariant: legitimate success and failure behavior must remain equivalent unless the defect itself requires a documented behavior change.
- Adversarial-certifier invariant: enforcement must resist alternate syntax, aliases, re-exports, and trivial structural evasion.
- Every defect remains active until legitimate reviewed closure. Remediation does not equal resolution.
