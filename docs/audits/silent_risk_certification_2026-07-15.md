# ConstructionSight Silent-Risk Certification Dossier

## Status

**Not certified. Independent adversarial review and final exact-tree certification remain mandatory.**

This dossier records correction and regression evidence for the active silent-risk defect ledger. It does not itself resolve any defect and does not authorize moving an entry from `governance/active_defects.toml` to `governance/resolved_defects.toml`.

The implementation review candidate is:

```text
27ae656605591a41aa1ac0ed53c18eecc8a04116
```

This audit document is intentionally one of the small set of post-review finalization artifacts excluded from the reviewed-tree digest. Changes here do not expand runtime, network, persistence, authorization, or product capability.

## Canonical exact-head evidence

GitHub Actions run `31668572471` (PR run #1028) explicitly checked out and verified the exact candidate SHA above on both supported Python versions.

### Python 3.11

- exact checkout identity: passed
- exact locked environment verification: passed
- dependency integrity: passed
- deterministic SBOM: passed
- vulnerability audit: no known vulnerabilities
- Ruff: passed
- strict mypy: passed across 243 source files
- compilation: passed
- warning-strict pytest: **1,096 / 1,096 passed**
- focused mutation certification: **13 / 13 mutants killed**
- adapter contract audit: passed
- source adapter coverage audit: passed
- diff hygiene: passed
- retained artifact: `certification-py311`, ID `9168895585`
- artifact ZIP digest: `sha256:7197186f1487398913f073ce5be88b317a921aa0cbe9e3b8a1edfb5d4514f029`

### Python 3.12

- exact checkout identity: passed
- exact locked environment verification: passed
- dependency integrity: passed
- deterministic SBOM: passed
- vulnerability audit: no known vulnerabilities
- Ruff: passed
- strict mypy: passed across 243 source files
- compilation: passed
- warning-strict pytest: **1,096 / 1,096 passed**
- focused mutation certification: **13 / 13 mutants killed**
- adapter contract audit: passed
- source adapter coverage audit: passed
- diff hygiene: passed
- retained artifact: `certification-py312`, ID `9168900581`
- artifact ZIP digest: `sha256:6dd7b3ccc7792949078ffa23d71ec9578a5a20d2e58872c0cf21d0a7457ef9b1`

Both runtime jobs produced the same repository-certification result: exactly 25 findings, consisting solely of active defects `CS-SR-001` through `CS-SR-024` plus `REVIEW-001` for the intentionally missing independent-review artifact. No additional architecture, capability, dependency, network, authorization, governance-shape, traceability, test-contract, source-audit, supply-chain, or tracked-tree finding remained.

The retained workflow artifacts expire under GitHub's configured seven-day retention and should be copied or independently re-generated before final certification if they are needed after expiration.

## Closure standard

For each defect below, four states are tracked conceptually:

1. **Correction present** — the runtime/governance implementation addresses the stated root cause.
2. **Regression evidence present** — focused tests or mechanical certification exercise the corrected boundary.
3. **Independent review pending/passed** — a separate adversarial reviewer has inspected the exact review-covered tree and all findings are resolved.
4. **Final certification pending/passed** — the final exact tree has zero active defects, a valid review artifact, and passes the complete locked Python 3.11/3.12 matrix.

At the time this dossier was created, states 1 and 2 are supported by the evidence described below, while states 3 and 4 remain pending for every active defect.

## Defect evidence matrix

### CS-SR-001 — Architecture

**Required resolution:** strict machine-readable layer/capability acquisition contract, AST import graph, exceptions, cycle checks, regression fixtures.

**Correction evidence:**

- `governance/architecture_contract.toml`
- `src/constructionsight/architecture_certification.py`
- `src/constructionsight/architecture_boundary_certification.py`
- explicit layer permissions, cycle prohibition, narrow expiring exceptions, and ADR-backed exception evidence

**Regression evidence:**

- `tests/test_architecture_boundary_certification.py`
- run #1028 produced no architecture findings on either supported runtime

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-002 — Capability traceability

**Required resolution:** strict capability registry and fail-closed tree reconciliation.

**Correction evidence:**

- `governance/capability_contract.toml`
- `src/constructionsight/traceability_certification.py`
- bidirectional capability ownership and default-owner reconciliation

**Regression evidence:**

- `tests/test_governance_link_certification.py`
- `tests/test_governance_certification.py`
- run #1028 produced no capability ownership or traceability findings

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-003 — Supply-chain reproducibility

**Required resolution:** pin declarations, artifact-hashed locks, governed inventory, immutable Action SHAs, vulnerability and SBOM gates.

**Correction evidence:**

- `governance/dependency_contract.toml`
- `requirements/py311.lock`
- `requirements/py312.lock`
- `src/constructionsight/dependency_certification.py`
- `src/constructionsight/supply_chain.py`
- immutable GitHub Action SHAs in `.github/workflows/ci.yml`

**Regression evidence:**

- `tests/test_dependency_certification.py`
- `tests/test_supply_chain.py`
- run #1028 exact lock verification, dependency integrity, deterministic SBOM, and vulnerability audit passed on both runtimes

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-004 — Network resilience inventory

**Required resolution:** complete approved transport inventory, AST enforcement, policy completeness, adversarial fixtures.

**Correction evidence:**

- `governance/network_contract.toml`
- `src/constructionsight/http_transport.py`
- `src/constructionsight/http_transport_models.py`
- architecture contract isolates approved transport modules and prohibits unapproved acquisition paths

**Regression evidence:**

- `tests/test_http_transport.py`
- `tests/test_semantic_authorization_certification.py`
- source-specific transport tests including CEQAnet and ArcGIS bounded-response paths
- run #1028 produced no network-contract or architecture transport findings

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-005 — Repository-wide authorization contract

**Required resolution:** general scope-bound authorization decision contract and classification of authority-bearing capability.

**Correction evidence:**

- `governance/authorization_contract.toml`
- `src/constructionsight/authorization_decision.py`
- `src/constructionsight/authorization_decision_models.py`
- operation-specific operator services and single-use preflight/claim behavior

**Regression evidence:**

- `tests/test_authorization_decision.py`
- `tests/test_semantic_authorization_certification.py`
- source, workflow, persistence, result-authority, and ArcGIS authorization tests registered in the adversarial matrix
- run #1028 produced no authorization findings beyond the intentionally active ledger

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-006 — Canonical certification breadth

**Required resolution:** deterministic certification of architecture, capability, dependency, network, authorization, adversarial-test, ADR, Action-pin, and review doctrine.

**Correction evidence:**

- `src/constructionsight/repository_certification_v2.py`
- `src/constructionsight/governance_certification.py`
- `src/constructionsight/governance_certification_core.py`
- architecture, dependency, authority, traceability, adversarial, and governance-shape certification modules

**Regression evidence:**

- `tests/test_repository_certification.py`
- `tests/test_governance_certification.py`
- `tests/test_governance_contract_schema.py`
- run #1028 canonical repository audit reduced to the deliberate ledger/review blockers only

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-007 — Independent adversarial review doctrine

**Required resolution:** high-risk classification, structured review schema, exact-head binding, unresolved-finding gate.

**Correction evidence:**

- ADR-0005 defines high-risk adversarial-review doctrine
- `src/constructionsight/authority_certification.py` enforces the structured independent-review artifact, passed status, exact fields, resolved findings, commit provenance, and reviewed-tree digest
- the implemented certification rule is stricter than a high-risk-only classifier: certification fails without independent review for the certified tree at all, so a high-risk change cannot evade review by misclassification

**Regression evidence:**

- `tests/test_review_binding_certification.py`
- missing review produces `REVIEW-001` in run #1028 as designed
- malformed/unresolved review and tree-tamper paths are mechanically rejected

**Closure state:** implementation/regression controls present; the required independent review itself is still pending and cannot be self-supplied.

### CS-SR-008 — Known dependency vulnerabilities

**Required resolution:** upgrade affected exact identities, update declarations/registry evidence, audit both Python environments, retain zero-vulnerability evidence.

**Correction evidence:**

- exact supported locks contain reviewed fixed dependency versions
- dependency contract and inventory are synchronized with the locks

**Regression evidence:**

- run #1028 vulnerability audit reported **no known vulnerabilities** on Python 3.11 and Python 3.12
- exact environment verification passed on both runtimes

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-009 — Logical lock-row parsing

**Required resolution:** one fail-closed logical-row parser across installation verification, SBOM, dependency agreement, and certification; multiline/unhashed regression fixtures.

**Correction evidence:**

- canonical dependency parsing and reconciliation reside in `src/constructionsight/dependency_certification.py` and `src/constructionsight/supply_chain.py`

**Regression evidence:**

- `tests/test_dependency_certification.py`
- `tests/test_supply_chain.py`
- run #1028 lock verification and SBOM generation passed for both locks

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-010 — Mutation certification absent from CI

**Required resolution:** run focused mutation certification in both CI jobs, retain deterministic report, include in aggregate gate.

**Correction evidence:**

- `.github/workflows/ci.yml` executes `constructionsight.mutation_certification` in each supported Python job and includes its outcome in aggregate enforcement

**Regression evidence:**

- `tests/test_mutation_detection.py`
- run #1028: **13 / 13 mutants killed** under Python 3.11 and Python 3.12
- mutation reports retained in both certification artifacts

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-011 — Exact-head CI evidence

**Required resolution:** canonical CI must execute and retain evidence for the exact final head.

**Correction evidence:**

- `.github/workflows/ci.yml` explicitly checks out `${{ github.event.pull_request.head.sha || github.sha }}`
- CI compares `git rev-parse HEAD` to the expected event SHA and aggregates that result as a mandatory gate

**Regression evidence:**

- `tests/test_ci_exact_head_contract.py`
- run #1028 verified expected and actual SHA as `27ae656605591a41aa1ac0ed53c18eecc8a04116` on both jobs

**Closure state:** exact-head mechanism/evidence present for the implementation candidate; final post-review exact-head certification still pending.

### CS-SR-012 — Installed-environment completeness

**Required resolution:** reject unexpected distributions, duplicates, malformed metadata, missing/mismatched ConstructionSight identity; govern bootstrap tooling.

**Correction evidence:**

- dependency contract declares expected project and bootstrap distributions
- `src/constructionsight/supply_chain.py` verifies exact installed inventory rather than only minimum locked presence

**Regression evidence:**

- `tests/test_supply_chain.py`
- run #1028 installed-distribution verification passed on both runtimes

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-013 — SBOM provenance

**Required resolution:** bind SBOM to one verified inventory snapshot, application root component, reviewed SHA-256 artifact identities, validated URLs, deterministic serial.

**Correction evidence:**

- `src/constructionsight/supply_chain.py`
- dependency contract declares deterministic CycloneDX output and reviewed package evidence

**Regression evidence:**

- `tests/test_supply_chain.py`
- deterministic SBOM generation passed on both run #1028 jobs

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-014 — Dependency-policy traceability

**Required resolution:** reject duplicate canonical identities, non-table entries, stale policy, unsafe paths; verify bootstrap/cross-lock/source/CI policy agreement.

**Correction evidence:**

- strict `governance/dependency_contract.toml`
- fail-closed dependency and governance-shape validation
- canonical CI commands are governed and pinned

**Regression evidence:**

- `tests/test_dependency_certification.py`
- `tests/test_governance_contract_schema.py`
- `tests/test_supply_chain.py`
- run #1028 produced no dependency-policy traceability findings

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-015 — Governance schema contraction/unknown fields

**Required resolution:** load every machine-readable governance surface and reject unknown/missing top-level fields and invalid defect/overlap/vulnerability identities.

**Correction evidence:**

- `src/constructionsight/governance_contract_schema.py`
- canonical certifier loads architecture, capability, dependency, network, authorization, adversarial-test, mutation, active/resolved defect, open-work, and vulnerability-exception contracts

**Regression evidence:**

- `tests/test_governance_contract_schema.py`
- run #1028 produced no governance-shape findings

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-016 — Cross-contract traceability

**Required resolution:** bidirectional governance reference graph for capability, network, authorization, dependency, and adversarial matrices.

**Correction evidence:**

- `src/constructionsight/governance_link_certification.py`
- capability ownership/policy/operation/test references are reconciled rather than parsed independently

**Regression evidence:**

- `tests/test_governance_link_certification.py`
- run #1028 produced no cross-contract traceability findings

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-017 — Adversarial-test contract doctrine

**Required resolution:** exact required categories, fields, safe test references, exclusions, and nonblank branch/mutation/property/concurrency doctrine.

**Correction evidence:**

- `governance/adversarial_test_contract.toml`
- `src/constructionsight/adversarial_contract_certification.py`

**Regression evidence:**

- `tests/test_adversarial_contract_certification.py`
- current matrix includes architecture, supply-chain, authorization, persistence, network, review-binding, and exact-head CI regression artifacts
- run #1028 produced no adversarial-contract finding

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-018 — CLI network/authorization bypass

**Required resolution:** prohibit CLI-to-transport imports; route live operations through application services requiring full scope-bound authority; Boolean confirmation only supplemental.

**Correction evidence:**

- architecture contract prohibits CLI-to-transport imports
- operation-specific services under `src/constructionsight/operator_services/`
- scope-bound authorization decisions/preflights govern live and mutating operations

**Regression evidence:**

- `tests/test_semantic_authorization_certification.py`
- operation-specific authorization tests for CEQAnet, ArcGIS, readiness, verification, promotion, registry, workflow, and result authority
- run #1028 produced no CLI-to-transport architecture or semantic-authorization finding

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-019 — Authorization construction defect

**Required resolution:** compute canonical digest identities before final model validation and add direct decision/preflight identity tests.

**Correction evidence:**

- `src/constructionsight/authorization_decision.py`
- `src/constructionsight/authorization_decision_models.py`

**Regression evidence:**

- `tests/test_authorization_decision.py`
- downstream operation-specific preflight/claim tests exercise constructible valid decisions

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-020 — Bounded-response enforcement

**Required resolution:** streamed byte ceilings, redirect denial before Location follow, terminal response classification, discard incomplete body evidence, regression coverage.

**Correction evidence:**

- `src/constructionsight/http_transport.py`
- CEQAnet listing/CSV/detail and source-verification transports route through bounded, fail-closed behavior

**Regression evidence:**

- `tests/test_http_transport.py`
- `tests/test_ceqanet_listing_executor.py`
- `tests/test_ceqanet_csv_live.py`
- source-specific oversize/redirect/terminal-failure tests

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-021 — CEQAnet intent/implementation divergence

**Required resolution:** one canonical listing model/service/executor/CLI, one-attempt doctrine, no direct CLI transport construction, import/runtime branch obligation.

**Correction evidence:**

- `src/constructionsight/ceqanet_listing_service.py`
- `src/constructionsight/adapters/ceqanet_listing_executor.py`
- `src/constructionsight/ceqanet_listing_execute_cli.py`
- governed CEQAnet model/endpoints alignment

**Regression evidence:**

- `tests/test_ceqanet_listing_service.py`
- `tests/test_ceqanet_listing_executor.py`
- `tests/test_ceqanet_listing_execute_cli.py`
- run #1028 full import/runtime suite passed

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-022 — Atomic CEQAnet persistence

**Required resolution:** prevalidate complete write plan, one transaction, rollback on any runtime failure, exact destination/plan authorization facade, zero-partial-commit tests.

**Correction evidence:**

- `src/constructionsight/ceqanet_persistence_execute.py`
- `src/constructionsight/operator_services/ceqanet_persistence_service.py`
- CLI delegates through the governed application service rather than using a bare Boolean as write authority

**Regression evidence:**

- `tests/test_ceqanet_persistence_execute.py`
- `tests/test_ceqanet_persistence_operator_service.py`
- `tests/test_ceqanet_persistence_execute_cli.py`

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-023 — Synchronization integrity

**Required resolution:** restore pure domain boundaries, application facades, test/CLI alignment, synchronize governance and PR metadata, obtain exact-head CI evidence.

**Correction evidence:**

- architecture and capability ownership were synchronized for parcel acquisition/verification/registry and intelligence identity-resolution modules
- application orchestration remains outside the pure domain boundary
- `docs/architecture/current_implementation_status.md` now reflects all 24 active defects
- PR #117 metadata is synchronized with the exact candidate and run #1028 result

**Regression evidence:**

- architecture/capability certification produced zero findings in run #1028
- 1,096 / 1,096 tests passed on both runtimes
- exact-head checkout was proven on both runtimes

**Closure state:** correction/regression present; independent review and final certification pending.

### CS-SR-024 — Independent-review topology binding

**Required resolution:** replace `HEAD^` topology dependence with deterministic reviewed-tree digest excluding only permitted finalization artifacts; retain commit provenance; reject other drift; test synthetic merge, shallow history/finalization/tamper behavior.

**Correction evidence:**

- `src/constructionsight/authority_certification.py` computes a deterministic review-covered index-tree digest and excludes only the explicit finalization allowlist
- reviewed commit remains provenance while tree equality is topology-independent
- non-permitted tracked changes invalidate review binding

**Regression evidence:**

- `tests/test_review_binding_certification.py`
- synthetic GitHub-style merge topology does not invalidate an equivalent reviewed tree
- permitted finalization changes are tolerated
- non-permitted production-tree change produces `REVIEW-009`

**Closure state:** correction/regression present; independent review and final certification pending.

## Independent review handoff

The independent reviewer must inspect the exact review-covered implementation tree rather than treating this dossier, the PR description, or green unit tests as proof.

The reviewer should independently challenge at minimum:

- layer ownership and architecture exceptions
- undeclared capability acquisition and boundary circumvention
- dependency identity, lock/hash provenance, unexpected installed code, Action pins, and SBOM claims
- network client inventory, redirects, byte ceilings, retries, terminal access-control behavior, and lawful-access boundaries
- authorization scope, negative authority, stale state, reuse/expiry, claim consumption, and Boolean bypass
- atomic mutation and rollback paths
- CEQAnet intent-to-implementation consistency
- ArcGIS bounded/rehearsal authority boundaries
- source-registry planning/apply separation
- mirrored tests, absent negative cases, mutation weaknesses, and concurrency/replay gaps
- exact-head CI behavior
- review-tree binding itself
- every active defect's stated root cause and required resolution

A passing artifact must satisfy the strict schema enforced by `src/constructionsight/authority_certification.py`. The reviewer must compute the reviewed-tree digest independently from the exact reviewed implementation checkout.

No implementing author or implementing assistant should represent its own work as the required independent adversarial review.

## Finalization sequence

After legitimate independent review passes:

1. add `governance/reviews/independent_review.json` with the reviewer identity, method, reviewed commit provenance, independently computed reviewed-tree digest, passed status, and only resolved findings;
2. update this dossier with the actual reviewer artifact and finding disposition;
3. move each defect from active to resolved only where the required resolution, regression evidence, and review disposition support closure;
4. ensure `governance/active_defects.toml` contains zero entries;
5. run canonical exact-head CI on the final head under Python 3.11 and Python 3.12;
6. require zero repository-certification findings and success of the aggregate quality gate in both jobs;
7. preserve final certification artifacts and their SHA-256 digests;
8. verify the intended merge/squash result is review-covered content-equivalent before any production-readiness claim;
9. only then mark PR #117 ready and reconcile the overlapping PR #116.

## Product continuation after hardening

Silent-risk hardening is a prerequisite to, not the completion of, the full ConstructionSight product.

After PR #117 is legitimately certified and merged, the next product phases remain:

- complete the verified recurring-live-source evidence required for CEQAnet maturity review;
- implement append-only authorization-consumption evidence and separately authorized county ArcGIS complete rehearsals;
- promote source maturity only from independently verified evidence;
- implement production ingestion/observation orchestration without weakening lawful-access or provenance boundaries;
- advance project-state intelligence and scoring from actual public-record signals;
- implement outreach preview/approval/deduplication/compliance evidence before any sending capability;
- implement the map/operator GUI, developer and general-contractor directories, jobsite views, relationship graph, evidence inspector, and lead queue;
- package the supported operator application only after the underlying ingestion and identity/authority controls justify it.

Those phases must remain separate from defect closure so product pressure cannot silently weaken the certification boundary.
