# ConstructionSight fix-only reconciliation — 2026-09-21

Hardening: `1a8f1b1e38e9f7ab11adcf629400fb4123c8ddf8`; tree `257c340cf6433938db17691806f1ebeb086b4294`. GUI: `a3392b8c1b7f44eb0c3c536b737bdae1420c646f`; tree `38d8292ff4ba1269b09d4e19f97c3afd1b366785`. Both GitHub drafts and the stacked base were re-read in this session. Local tracked blobs and complete trees were checked against GitHub object identities. Local history is shallow; reviewed-history certification must use complete history in canonical CI.

## Disposition and limits

All 74 original ledger entries are accounted for: 41 correction evidenced, 25 partially corrected, 8 unresolved. One additional confirmed defect, CS-SR-075, is recorded below. **Zero entries are closed.**

“Correction evidenced” means the mapped code implements the identified corrective mechanism and matching regression evidence exists and passed at the stated source checkpoint. It does not mean a fresh complete-tree review found no alternate path, that unrelated gates passed, or that the defect can move to the resolved ledger. Partial and unresolved entries list concrete remaining requirements. Related tests are not represented as closure evidence for a requirement they do not test. Mapped mutation IDs identify implemented focused witnesses, not comprehensive mutation coverage.

## Retained starting verification

- Hardening CI [35581631150](https://github.com/TruSudo/Construction-Sight/actions/runs/35581631150): Python 3.11/3.12 each passed 1,522 tests and killed 115/115 focused mutants. Strict mypy passed on 261 source files. Both isolated vulnerability jobs passed. **Ruff failed with nine errors; structural preflight failed on CERT-SUPPRESS-001; aggregate certification remained blocked.**
- GUI CI [35581674671](https://github.com/TruSudo/Construction-Sight/actions/runs/35581674671): Python 3.11/3.12 each passed 1,626 tests and killed 115/115 focused mutants. Strict mypy passed on 271 source files. Both isolated vulnerability jobs passed. The nine shared lint failures and forbidden skip remain; the GUI also has an import-order violation in `source_candidate_docket_service.py`, for ten lint errors total.
- Raw job logs were fetched for all eight jobs; continue-on-error step conclusions were not treated as actual successful outcomes. Jobs: 106275606358, 106275606604, 106275606669, 106275606672, 106275742262, 106275742457, 106275742728, 106275742911.
- Local warning-strict hardening baseline: 1,522 passed in 25.10 seconds. This diagnostic Python 3.12.14 environment reuses available dependencies and is **not** exact-lock release evidence (among other mismatches, AnyIO 4.9.0 and pip 25.0.1). No production source collection was performed.
- Codex Security is installed, but this session exposes no callable Security workflow tools. No Security review or context-isolated pass is claimed.

## Dependency-aware execution order

Evaluate CS-SR-054 first and centralize safe evidence handles, canonical names, bounded reads and publication. Correct CS-SR-075 while preserving the adverse tests. Use that foundation for CS-SR-055 and CS-SR-058, then bind real durable effects and competing business transitions under CS-SR-061/050. Resolve source access/provenance/identity/eligibility before duplicate/workflow finalization; reconcile append-only ledgers, exact monetary/content identities, schema compatibility and deep immutability against their consumers. Only after all implementation gaps are remedied can the five-pass frozen-tree campaign begin.

## Complete original inventory and new finding

| Defect | Severity | Disposition | Area |
|---|---|---|---|
| CS-SR-001 | P1 | correction evidenced | architecture |
| CS-SR-002 | P1 | correction evidenced | capability-traceability |
| CS-SR-003 | P1 | correction evidenced | supply-chain |
| CS-SR-004 | P1 | correction evidenced | network-resilience |
| CS-SR-005 | P1 | correction evidenced | authorization |
| CS-SR-006 | P1 | correction evidenced | certification |
| CS-SR-007 | P2 | partially corrected | independent-review |
| CS-SR-008 | P0 | correction evidenced | supply-chain-vulnerability |
| CS-SR-009 | P1 | correction evidenced | dependency-certification |
| CS-SR-010 | P1 | correction evidenced | adversarial-testing |
| CS-SR-011 | P0 | partially corrected | exact-head-ci |
| CS-SR-012 | P1 | correction evidenced | installed-environment-inventory |
| CS-SR-013 | P1 | correction evidenced | sbom-provenance |
| CS-SR-014 | P1 | correction evidenced | dependency-policy-traceability |
| CS-SR-015 | P1 | correction evidenced | governance-schema |
| CS-SR-016 | P1 | correction evidenced | cross-contract-traceability |
| CS-SR-017 | P1 | correction evidenced | adversarial-contract-doctrine |
| CS-SR-018 | P0 | partially corrected | network-authorization-architecture |
| CS-SR-019 | P0 | correction evidenced | authorization-construction |
| CS-SR-020 | P0 | correction evidenced | bounded-response-enforcement |
| CS-SR-021 | P0 | correction evidenced | intent-implementation-divergence |
| CS-SR-022 | P0 | correction evidenced | atomic-persistence |
| CS-SR-023 | P0 | partially corrected | synchronization-integrity |
| CS-SR-024 | P0 | correction evidenced | independent-review-binding |
| CS-SR-025 | P0 | correction evidenced | independent-review-worktree-binding |
| CS-SR-026 | P0 | correction evidenced | defect-closure-ledger-integrity |
| CS-SR-027 | P0 | partially corrected | independent-review-identity-authenticity |
| CS-SR-028 | P0 | correction evidenced | defect-closure-fact-integrity |
| CS-SR-029 | P0 | correction evidenced | http-url-canonicalization |
| CS-SR-030 | P0 | correction evidenced | persistence-authorization-toctou |
| CS-SR-031 | P0 | correction evidenced | ci-environment-identity |
| CS-SR-032 | P0 | correction evidenced | ceqanet-redirect-doctrine |
| CS-SR-033 | P0 | correction evidenced | repository-evidence-containment |
| CS-SR-034 | P0 | partially corrected | semantic-authorization-proof |
| CS-SR-035 | P0 | correction evidenced | network-query-authority |
| CS-SR-036 | P0 | correction evidenced | supply-chain-vulnerability |
| CS-SR-037 | P0 | correction evidenced | http-exact-request-identity |
| CS-SR-038 | P0 | correction evidenced | http-response-evidence-integrity |
| CS-SR-039 | P0 | correction evidenced | http-environment-and-transport-authority |
| CS-SR-040 | P0 | correction evidenced | arcgis-exact-request-and-evidence-integrity |
| CS-SR-041 | P0 | correction evidenced | arcgis-bounded-response-enforcement |
| CS-SR-042 | P1 | correction evidenced | network-media-type-contract-drift |
| CS-SR-043 | P0 | partially corrected | effect-implementation-authority |
| CS-SR-044 | P0 | partially corrected | trusted-time-authority |
| CS-SR-045 | P0 | unresolved | lawful-access-fact-authority |
| CS-SR-046 | P0 | unresolved | epistemic-provenance-authority |
| CS-SR-047 | P1 | unresolved | derived-identity-integrity |
| CS-SR-048 | P0 | unresolved | operational-confidence-gating |
| CS-SR-049 | P0 | unresolved | duplicate-review-gate |
| CS-SR-050 | P0 | partially corrected | business-transition-concurrency |
| CS-SR-051 | P1 | partially corrected | historical-ledger-separation |
| CS-SR-052 | P1 | unresolved | result-ledger-content-identity |
| CS-SR-053 | P1 | unresolved | financial-decimal-integrity |
| CS-SR-054 | P0 | partially corrected | runtime-evidence-containment |
| CS-SR-055 | P1 | partially corrected | pre-materialization-resource-bounds |
| CS-SR-056 | P1 | unresolved | database-schema-evolution |
| CS-SR-057 | P1 | partially corrected | foundational-domain-invariants |
| CS-SR-058 | P0 | partially corrected | cross-artifact-commit-atomicity |
| CS-SR-059 | P1 | partially corrected | deep-content-immutability |
| CS-SR-060 | P0 | partially corrected | public-source-egress-authority |
| CS-SR-061 | P0 | partially corrected | effect-consumption-atomicity |
| CS-SR-062 | P0 | correction evidenced | assurance-reviewed-tree-binding |
| CS-SR-063 | P0 | correction evidenced | assurance-context-isolation-integrity |
| CS-SR-064 | P0 | correction evidenced | assurance-source-provenance-integrity |
| CS-SR-065 | P2 | partially corrected | assurance-quality-gate-compliance |
| CS-SR-066 | P0 | correction evidenced | assurance-owner-acceptance-authenticity |
| CS-SR-067 | P2 | partially corrected | assurance-quality-gate-compliance |
| CS-SR-068 | P1 | partially corrected | supply-chain-action-runtime-provenance |
| CS-SR-069 | P1 | correction evidenced | supply-chain-vulnerability-toolchain-reproducibility |
| CS-SR-070 | P2 | partially corrected | assurance-quality-gate-compliance |
| CS-SR-071 | P0 | partially corrected | assurance-execution-integrity |
| CS-SR-072 | P0 | partially corrected | ci-inherited-execution-controls |
| CS-SR-073 | P0 | partially corrected | ci-pre-gate-build-execution |
| CS-SR-074 | P0 | partially corrected | supply-chain-newly-disclosed-anyio-advisories |
| CS-SR-075 | P1 | unresolved | artifact-remediation-quality-regression |

## CS-SR-001 — P1 — correction evidenced

**Original root cause:** No strict machine-readable layer and capability-acquisition contract is enforced across the tracked production tree.

**Required resolution (unaltered ledger text):** Add exact module classification, AST import graph, capability permissions, exceptions, cycle checks, and regression fixtures.

**Current assessment and remaining actions:** Exact layer classification, capability permissions, import edges, cycles and bounded exceptions are enforced. Reverse-import, network-acquisition and cycle regressions pass.

**Implementation references:**

- `src/constructionsight/architecture_certification.py`: `_audit_architecture` (line 32).

**Regression and integration references:**

- `tests/test_governance_certification.py` (14 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-002 — P1 — correction evidenced

**Original root cause:** Implemented, guarded, planned, and deprecated capabilities are documented but not cross-checked against production modules, tests, doctrine, authority, and future entry conditions.

**Required resolution (unaltered ledger text):** Add a strict capability registry and fail-closed tree reconciliation.

**Current assessment and remaining actions:** Capability owners, runtime status, tests, documentation and entry conditions are reconciled by the registry audit; planned runtime exposure is rejected.

**Implementation references:**

- `src/constructionsight/traceability_certification.py`: `_audit_capabilities` (line 56).

**Regression and integration references:**

- `tests/test_governance_certification.py` (14 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-003 — P1 — correction evidenced

**Original root cause:** Direct dependencies use open-ended minimum versions, CI installs with resolver-selected upgrades, and third-party Actions use mutable major tags.

**Required resolution (unaltered ledger text):** Pin declarations, add governed artifact-hashed locks and inventory, pin Actions to immutable SHAs, and add vulnerability/SBOM gates.

**Current assessment and remaining actions:** Exact declarations, wheel hashes, immutable Actions and SBOM/vulnerability jobs exist. Both current-head vulnerability matrices pass. Whole release qualification remains blocked by CS-SR-075 and assurance.

**Implementation references:**

- `src/constructionsight/dependency_certification.py`: `audit_dependencies` (line 463).
- `src/constructionsight/ci_action_certification.py`: `audit_ci_actions` (line 72).
- `src/constructionsight/supply_chain.py`: `load_lock_entries` (line 93).

**Regression and integration references:**

- `tests/test_dependency_certification.py` (18 test functions in the passing starting suite).
- `tests/test_ci_action_certification.py` (5 test functions in the passing starting suite).
- `tests/test_supply_chain.py` (18 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-DEPENDENCY-DRIFT-001`, `CS-MUT-ASSURANCE-CI-ACTION-COMMIT-001`, `CS-MUT-ASSURANCE-CI-ACTION-REVIEW-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-004 — P1 — correction evidenced

**Original root cause:** Network boundaries are individually hardened but no complete inventory mechanically rejects unapproved clients or requests without a declared policy.

**Required resolution (unaltered ledger text):** Add a network contract, approved transport classification, AST enforcement, policy completeness checks, and adversarial fixtures.

**Current assessment and remaining actions:** Transport module inventory, exact policy ownership and policy fields are checked; unapproved clients and incomplete policy regressions pass. Destination-specific authority is separately assessed under CS-SR-060.

**Implementation references:**

- `src/constructionsight/architecture_boundary_certification.py`: `audit_architecture_boundaries` (line 14).
- `src/constructionsight/authority_certification.py`: `_audit_network` (line 40).

**Regression and integration references:**

- `tests/test_architecture_boundary_certification.py` (3 test functions in the passing starting suite).
- `tests/test_governance_certification.py` (14 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ARCH-BYPASS-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-005 — P1 — correction evidenced

**Original root cause:** Strong feature-specific authorization exists, including PR #116, but no repository-wide decision contract and mutation inventory mechanically prevents boolean-only or scope-free authority.

**Required resolution (unaltered ledger text):** Add a general scope-bound authorization decision contract and classify every authority-bearing capability.

**Current assessment and remaining actions:** Strict content-bound decisions and preflights represent scope, identity, state, expiry, denied authority and audit identity. Boolean-only authority is rejected; consumption completeness is assessed under CS-SR-061.

**Implementation references:**

- `src/constructionsight/authorization_decision.py`: `build_authorization_decision` (line 40), `validate_authorization_decision` (line 93).
- `src/constructionsight/authority_certification.py`: `_audit_authorization` (line 172).

**Regression and integration references:**

- `tests/test_authorization_decision.py` (7 test functions in the passing starting suite).
- `tests/test_local_operator_authorization.py` (5 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-AUTH-EXPIRY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-006 — P1 — correction evidenced

**Original root cause:** The canonical certifier does not yet enforce architecture, capability, dependency, network, authorization, adversarial-test, ADR, action-pin, or review doctrine.

**Required resolution (unaltered ledger text):** Expand deterministic certification and CI with stable finding codes and fail-closed governance parsing.

**Current assessment and remaining actions:** Canonical certification runs the added governance and semantic auditors with stable finding codes. Its actual rejection of the new forbidden skip demonstrates that an ordinary passing pytest run does not bypass it.

**Implementation references:**

- `src/constructionsight/governance_certification.py`: `audit_governance` (line 290).
- `src/constructionsight/repository_certification_v2.py`: `certify_repository` (line 38).

**Regression and integration references:**

- `tests/test_governance_certification.py` (14 test functions in the passing starting suite).
- `tests/test_repository_certification_v2.py` (4 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ARCH-BOUNDARY-WIRING-001`, `CS-MUT-ASSURANCE-CI-PERMISSIONS-V2-WIRING-001`, `CS-MUT-ASSURANCE-CI-ACTION-V2-WIRING-001`, `CS-MUT-VULNERABILITY-FINAL-001`, `CS-MUT-CI-EXECUTION-FINAL-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-007 — P2 — partially corrected

**Original root cause:** High-risk changes lack a mandatory structured independent adversarial review artifact tied to the exact head.

**Required resolution (unaltered ledger text):** Add high-risk classification, review schema, exact-head binding, and unresolved-finding gate.

**Current assessment and remaining actions:** Exact-tree review schemas and unresolved-candidate gates exist. ADR-0009 now requires Native Maximum Assurance rather than mandatory external-human review. No authentic complete five-pass artifact exists, so the operational review requirement is unmet.

**Implementation references:**

- `src/constructionsight/assurance_certification.py`: `audit_assurance_review` (line 1398).
- `src/constructionsight/github_review_certification.py`: `verify_github_review_binding` (line 40).

**Regression and integration references:**

- `tests/test_assurance_certification.py` (20 test functions in the passing starting suite).
- `tests/test_github_review_certification.py` (12 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-FRESH-CONTEXT-001`, `CS-MUT-ASSURANCE-DEEP-COUNT-001`, `CS-MUT-ASSURANCE-DEFERRED-CANDIDATE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-COVERAGE-GAP-001`, `CS-MUT-ASSURANCE-SURVIVING-MUTANT-001`, `CS-MUT-ASSURANCE-PASS-EVIDENCE-001`, `CS-MUT-ASSURANCE-GATE-EVIDENCE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-CONTEXT-AGGREGATION-001`, `CS-MUT-ASSURANCE-SOURCE-DIGEST-001`, `CS-MUT-ASSURANCE-SOURCE-COMMIT-001`, `CS-MUT-ASSURANCE-SOURCE-REUSE-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-008 — P0 — correction evidenced

**Original root cause:** The first exact supported-environment audit found known vulnerabilities in Click 8.2.1, IDNA 3.10, pip 25.1.1, Pygments 2.19.2, and pytest 8.4.1.

**Required resolution (unaltered ledger text):** Upgrade only the affected exact identities to reviewed fixed releases, update declarations and registry evidence, rerun both Python audits, and retain zero-vulnerability reports.

**Current assessment and remaining actions:** The originally vulnerable locked identities have changed and both current-head supported-runtime vulnerability jobs succeed. Raw job evidence, rather than the old discovery head, is the relevant audit checkpoint.

**Implementation references:**

- `src/constructionsight/supply_chain.py`: `load_lock_entries` (line 93).
- `src/constructionsight/vulnerability_certification.py`: `certify` (line 196).

**Regression and integration references:**

- `tests/test_supply_chain.py` (18 test functions in the passing starting suite).
- `tests/test_vulnerability_certification.py` (16 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-VULNERABILITY-ACTIVE-001`, `CS-MUT-VULNERABILITY-DIGEST-001`, `CS-MUT-VULNERABILITY-RELEASE-001`, `CS-MUT-VULNERABILITY-MANIFEST-001`, `CS-MUT-VULNERABILITY-DUPLICATE-001`, `CS-MUT-VULNERABILITY-INVENTORY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-009 — P1 — correction evidenced

**Original root cause:** The canonical dependency audit parsed lock files one physical line at a time, so secure backslash-continued artifact hashes would be misclassified or omitted from direct-dependency reconciliation.

**Required resolution (unaltered ledger text):** Use one fail-closed logical-row parser for installation verification, SBOM generation, dependency agreement, and canonical certification; add multiline and unhashed regression fixtures.

**Current assessment and remaining actions:** One logical-row hash parser supplies lock installation checks, inventory/SBOM and canonical agreement; multiline and malformed-row regressions pass.

**Implementation references:**

- `src/constructionsight/supply_chain.py`: `_logical_lock_rows` (line 59), `load_lock_entries` (line 93).
- `src/constructionsight/dependency_certification.py`: `audit_dependency_agreement` (line 694).

**Regression and integration references:**

- `tests/test_supply_chain.py` (18 test functions in the passing starting suite).
- `tests/test_dependency_certification.py` (18 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-DEPENDENCY-DRIFT-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-010 — P1 — correction evidenced

**Original root cause:** A focused mutation certifier and mutation contract existed in production code, but the Python CI matrix did not execute or enforce its result.

**Required resolution (unaltered ledger text):** Execute focused mutation certification in both supported Python CI jobs, retain its deterministic report, and include its outcome in the aggregate fail-closed quality gate.

**Current assessment and remaining actions:** Both supported CI quality jobs execute the controlled mutation campaign and report 115/115 killed. These are focused witnesses, not proof that the full defect inventory is corrected.

**Implementation references:**

- `src/constructionsight/mutation_certification.py`: `run_mutation_certification` (line 315).

**Regression and integration references:**

- `tests/test_mutation_detection.py` (4 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-011 — P0 — partially corrected

**Original root cause:** No pull-request workflow run or commit status is associated with the current hardening heads after branch updates and a draft PR reopen, while a prior branch head remains observable through the same GitHub API. Exact-head CI evidence therefore does not exist for the current tree.

**Required resolution (unaltered ledger text):** Trigger the canonical CI workflow through a non-suppressed pull-request event or explicit workflow dispatch on the final exact head; require both Python jobs and retained certification artifacts before any defect resolution or merge.

**Current assessment and remaining actions:** Canonical pull-request runs exist at both exact heads, so the original missing-run condition is absent. Both quality jobs still fail lint/preflight and aggregate enforcement; rerun and retain the complete matrix after corrections.

**Implementation references:**

- `src/constructionsight/ci_execution_certification.py`: `audit_ci_execution` (line 128).

**Regression and integration references:**

- `tests/test_ci_exact_head_contract.py` (4 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-012 — P1 — correction evidenced

**Original root cause:** Installed-version verification required locked distributions but did not reject additional installed distributions, duplicate installed metadata, or a missing/mismatched ConstructionSight distribution. Undeclared code could therefore remain importable while absent from the certified inventory.

**Required resolution (unaltered ledger text):** Reject every installed distribution outside the exact lock and exact ConstructionSight project identity; include bootstrap tooling in the lock; reject duplicate/malformed installed metadata; add adversarial fixtures.

**Current assessment and remaining actions:** Unexpected, duplicate and malformed installed distributions and installed-project shadowing are rejected. Source identity is checked without building the candidate under the later CS-SR-073 contract.

**Implementation references:**

- `src/constructionsight/supply_chain.py`: `installed_inventory` (line 163), `_verification_report` (line 222), `_source_project` (line 182).

**Regression and integration references:**

- `tests/test_supply_chain.py` (18 test functions in the passing starting suite).
- `tests/test_supply_chain_source_tree.py` (4 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-013 — P1 — correction evidenced

**Original root cause:** The deterministic SBOM represented only locked package versions, omitted reviewed artifact hashes, could use an unsupported PyPI project identity for the local application, parsed project metadata URLs imprecisely, and took a second inventory snapshot after verification.

**Required resolution (unaltered ledger text):** Bind the SBOM to one verified inventory snapshot, include the local application as the root generic component, include approved SHA-256 artifact identities for locked libraries, validate external URLs, and generate a deterministic standards-conformant serial.

**Current assessment and remaining actions:** SBOM construction uses verified inventory, reviewed artifact hashes and a generic source-project root with deterministic provenance. Current CI SBOM and identity gates execute successfully.

**Implementation references:**

- `src/constructionsight/supply_chain.py`: `build_sbom` (line 402), `_component` (line 356), `_source_component` (line 390).

**Regression and integration references:**

- `tests/test_supply_chain.py` (18 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-014 — P1 — correction evidenced

**Original root cause:** Dependency registry and top-level policy validation could silently collapse duplicate canonical identities, discard non-table entries, accept stale hash-policy statements, permit unsafe lock paths, and omit checks that CI actually enforces the declared installation and mutation gates.

**Required resolution (unaltered ledger text):** Fail closed on unknown/missing top-level fields, canonical and duplicate registry identities, non-table entries, required policy values, safe artifact paths, bootstrap and cross-lock agreement, authoritative source URLs, and mandatory CI commands.

**Current assessment and remaining actions:** Strict policy keys, canonical identities, safe paths, artifact hashes, registry agreement and executable CI installation/mutation obligations are enforced with negative fixtures.

**Implementation references:**

- `src/constructionsight/dependency_certification.py`: `_audit_contract_policy` (line 156), `_audit_registry_entry` (line 337), `_audit_ci_environment_identity` (line 245).

**Regression and integration references:**

- `tests/test_dependency_certification.py` (18 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-DEPENDENCY-DRIFT-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-015 — P1 — correction evidenced

**Original root cause:** Schema versions were checked, but unknown or misspelled top-level fields across architecture, capability, network, authorization, adversarial-test, mutation, defect, overlap, and vulnerability-exception contracts could remain inert without a finding. Mutation, overlap, and vulnerability-exception contracts were not loaded by canonical repository certification.

**Required resolution (unaltered ledger text):** Load every machine-readable governance surface in the canonical certifier; enforce exact top-level fields and nonexpansion boundaries; validate active-defect, overlap, and vulnerability-exception identities; add negative fixtures.

**Current assessment and remaining actions:** Canonical loading covers the machine-readable surfaces and rejects unknown fields, malformed identities, invalid exceptions and boundary contraction. Current retained finding output is consistent with enforcement.

**Implementation references:**

- `src/constructionsight/governance_contract_schema.py`: `audit_governance_contract_shapes` (line 684).
- `src/constructionsight/governance_certification.py`: `audit_governance` (line 290).

**Regression and integration references:**

- `tests/test_governance_contract_schema.py` (11 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-016 — P1 — correction evidenced

**Original root cause:** Capability, network-policy, authorization-operation, dependency, and adversarial-matrix references were independently parsed but not bidirectionally reconciled. Invented references, orphaned policies, and capabilities omitted from adversarial matrices could therefore survive certification.

**Required resolution (unaltered ledger text):** Build a bidirectional governance reference graph; require exact policy and operation ownership, valid dependency capability references, and adversarial matrix coverage for every registered capability; add orphan and invented-reference fixtures.

**Current assessment and remaining actions:** Bidirectional references reject invented capability, dependency, policy and operation identities and orphaned ownership; matching negative fixtures pass.

**Implementation references:**

- `src/constructionsight/governance_link_certification.py`: `audit_governance_links` (line 23).

**Regression and integration references:**

- `tests/test_governance_link_certification.py` (5 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-017 — P1 — correction evidenced

**Original root cause:** Adversarial matrices could accept unknown fields, category contraction or invention, unsafe or missing test references, malformed exclusions, and empty prose obligations while still appearing to cover all required risk classes.

**Required resolution (unaltered ledger text):** Enforce the exact mandatory category set, exact matrix and exclusion fields, canonical lists, safe existing test paths, complete category coverage or justified exclusion, and nonblank branch/mutation/property/concurrency doctrine; add negative fixtures.

**Current assessment and remaining actions:** The exact 17-category doctrine is backed by node-level witnesses and declared mutants; unknown fields, unsafe references, malformed exclusions and missing obligations are rejected.

**Implementation references:**

- `src/constructionsight/adversarial_contract_certification.py`: `audit_adversarial_contract` (line 289), `_audit_witnesses` (line 113).

**Regression and integration references:**

- `tests/test_adversarial_contract_certification.py` (9 test functions in the passing starting suite).
- `tests/test_adversarial_semantic_witnesses.py` (6 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-018 — P0 — partially corrected

**Original root cause:** Multiple live CLI paths import approved transport modules directly and use bare Boolean flags such as --execute-live as the operative network grant, bypassing canonical application services and the general scope-bound authorization decision contract.

**Required resolution (unaltered ledger text):** Prohibit CLI-to-transport imports; inventory every live CLI path; move each operation behind an application service that requires exact actor, action, resource, scope, current state, validity, denied authority, audit identity, and single-use preflight; retain Boolean confirmation only as an additional gate.

**Current assessment and remaining actions:** CLI transport imports and named high-impact services are guarded by decision/validation/consumption analysis. Source-registry durable publication still occurs after the facade reserves only an in-memory calculation; complete actual effect coverage must be reconciled with CS-SR-061.

**Implementation references:**

- `src/constructionsight/semantic_authorization_certification.py`: `audit_semantic_authorization` (line 1110).
- `src/constructionsight/ceqanet_listing_service.py`: `execute_authorized_ceqanet_listing` (line 179).

**Regression and integration references:**

- `tests/test_semantic_authorization_certification.py` (21 test functions in the passing starting suite).
- `tests/test_ceqanet_listing_service.py` (6 test functions in the passing starting suite).
- `tests/test_ceqanet_csv_operator_service.py` (5 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-AUTH-EFFECT-TARGET-001`, `CS-MUT-CONSUME-CALLER-LEDGER-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-019 — P0 — correction evidenced

**Original root cause:** The general authorization builders validated placeholder all-zero decision and preflight IDs before computing the content digest, so valid scope-bound decisions and preflights could not be constructed.

**Required resolution (unaltered ledger text):** Construct canonical identity payloads without running final digest validators, compute the real digest, validate the completed model, and add direct decision/preflight identity regression coverage.

**Current assessment and remaining actions:** Builders compute real digests before final model validation. Direct decision/preflight construction and identity-tamper regressions pass.

**Implementation references:**

- `src/constructionsight/authorization_decision.py`: `_decision_identity_payload` (line 20), `_preflight_identity_payload` (line 30), `build_authorization_decision` (line 40).

**Regression and integration references:**

- `tests/test_authorization_decision.py` (7 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-AUTH-EXPIRY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-020 — P0 — correction evidenced

**Original root cause:** CEQAnet listing and CSV paths followed redirects or materialized complete response bodies before enforcing declared size ceilings, so untrusted response bytes could exceed policy before rejection.

**Required resolution (unaltered ledger text):** Route production listing and CSV requests through the streamed bounded HTTP engine, deny redirects before following Location, stop reading at the byte ceiling, classify terminal responses, discard incomplete body evidence, and add redirect and oversize regressions.

**Current assessment and remaining actions:** Listing and CSV use streamed byte limits and deny redirects before follow-up requests. Declared-length/chunked oversize and terminal response fixtures pass without incomplete success evidence.

**Implementation references:**

- `src/constructionsight/http_transport.py`: `_read_bounded` (line 384), `execute_bounded_http` (line 461).

**Regression and integration references:**

- `tests/test_http_transport.py` (26 test functions in the passing starting suite).
- `tests/test_ceqanet_csv_live.py` (12 test functions in the passing starting suite).
- `tests/test_ceqanet_listing_executor.py` (8 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-021 — P0 — correction evidenced

**Original root cause:** The CEQAnet listing application service imported a nonexistent model generation while the live CLI bypassed that service and constructed the legacy executor directly, allowing documented architecture and executable behavior to diverge.

**Required resolution (unaltered ledger text):** Reconcile the listing plan, executor, service, CLI, and tests around one canonical model; enforce one-attempt retry doctrine; prohibit direct CLI transport construction; and add an import/runtime branch obligation that detects nonexistent service dependencies.

**Current assessment and remaining actions:** The service imports valid canonical models and the CLI routes through it; import/runtime and zero-extra-retry fixtures pass.

**Implementation references:**

- `src/constructionsight/ceqanet_listing_service.py`: `execute_authorized_ceqanet_listing` (line 179).

**Regression and integration references:**

- `tests/test_ceqanet_listing_service.py` (6 test functions in the passing starting suite).
- `tests/test_ceqanet_listing_executor.py` (8 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-022 — P0 — correction evidenced

**Original root cause:** CEQAnet persistence execution could commit valid operations while reporting other operations as failed or skipped, and the CLI treated a bare Boolean as the operative write grant.

**Required resolution (unaltered ledger text):** Prevalidate the complete reviewed write plan, execute all operations in one transaction, roll back on any runtime failure, route the CLI through an exact plan-and-destination authorization facade, and retain zero-partial-commit regressions.

**Current assessment and remaining actions:** Complete write plans are prevalidated, detached and applied transactionally through the scoped facade; mid-transaction failure rolls back earlier writes. Whole runtime publication is not implied by this database result.

**Implementation references:**

- `src/constructionsight/ceqanet_persistence_execute.py`: `CeqanetPersistenceExecutionResult` (line 30), `_PreparedOperation` (line 78), `execute_ceqanet_write_plan` (line 86), `validate_ceqanet_write_plan` (line 132), `_prepare_operations` (line 139), `_validate_write_plan_envelope` (line 191).

**Regression and integration references:**

- `tests/test_ceqanet_persistence_execute.py` (7 test functions in the passing starting suite).
- `tests/test_ceqanet_persistence_operator_service.py` (7 test functions in the passing starting suite).
- `tests/test_adversarial_semantic_witnesses.py` (6 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-023 — P0 — partially corrected

**Original root cause:** Sequential hardening commits left tests importing application functions that were not committed, placed authorization logic inside a domain-classified planning module, and allowed PR and governance inventories to lag the actual branch.

**Required resolution (unaltered ledger text):** Restore pure domain boundaries, add application-layer facades, align every test import and CLI call, synchronize mutation/adversarial/capability/defect contracts and PR metadata, and obtain exact-head CI evidence before resolution.

**Current assessment and remaining actions:** Module/service wiring tests pass, but hardening implementation-status documentation still reports 38 active defects and older review language. Current draft descriptions also contain stale checkpoints; reconcile current documentation and PR status after the verified fixes.

**Implementation references:**

- `src/constructionsight/semantic_authorization_certification.py`: `audit_semantic_authorization` (line 1110).
- `src/constructionsight/governance_link_certification.py`: `audit_governance_links` (line 23).

**Regression and integration references:**

- `tests/test_semantic_authorization_certification.py` (21 test functions in the passing starting suite).
- `tests/test_governance_link_certification.py` (5 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-AUTH-EFFECT-TARGET-001`, `CS-MUT-CONSUME-CALLER-LEDGER-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-024 — P0 — correction evidenced

**Original root cause:** The independent-review certifier binds reviewed_commit to HEAD^ and diffs reviewed_commit..HEAD, but canonical pull-request CI checks out a shallow synthetic merge ref whose first parent is main rather than the reviewed branch implementation. A legitimate review can therefore fail solely because of GitHub merge topology, and the binding is not stable across an equivalent squash-merged tree.

**Required resolution (unaltered ledger text):** Replace parent-topology binding with a deterministic reviewed-tree digest that covers every tracked path except explicitly permitted post-review governance artifacts; retain reviewed commit provenance; reject any non-permitted tree drift; and add synthetic-merge, shallow-history, allowed-finalization, and tamper regressions.

**Current assessment and remaining actions:** Assurance binds the covered tree independently of HEAD-parent topology. Synthetic merge, permitted finalization and committed implementation-tamper regressions pass.

**Implementation references:**

- `src/constructionsight/assurance_certification.py`: `assured_tree_digest` (line 442), `audit_assurance_review` (line 1398).

**Regression and integration references:**

- `tests/test_review_binding_certification.py` (14 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-025 — P0 — correction evidenced

**Original root cause:** The reviewed-tree digest is computed from Git index object identities without first rejecting dirty non-permitted worktree state. A reviewer could therefore compute a digest that represents the committed index while inspecting or executing unstaged, staged, or untracked non-permitted content not represented by that digest.

**Required resolution (unaltered ledger text):** Make reviewed-tree digest computation fail closed when any staged, unstaged, or untracked path exists outside the explicit post-review finalization allowlist; retain permitted finalization behavior; and add staged, unstaged, untracked, and allowed-path regression coverage.

**Current assessment and remaining actions:** Covered-tree computation rejects staged, unstaged and untracked non-finalization changes; narrowly permitted finalization remains supported and tested.

**Implementation references:**

- `src/constructionsight/assurance_certification.py`: `_assert_assurance_worktree_clean` (line 418), `assured_tree_digest` (line 442).

**Regression and integration references:**

- `tests/test_review_binding_certification.py` (14 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-026 — P0 — correction evidenced

**Original root cause:** Canonical governance-shape certification validates active defect entries but does not validate resolved defect entry shape, evidence paths, resolution provenance, duplicate IDs, or active/resolved disjointness. The ledger comment also requires exact-tree certification before a defect can move to resolved even though exact-tree certification is mechanically blocked while any defect remains active, creating a circular and unenforceable closure rule.

**Required resolution (unaltered ledger text):** Define and enforce an exact resolved-defect evidence schema; require unique IDs, full discovery and resolution commit provenance, nonblank resolution summary, safe existing regression/evidence paths, independent-review binding, and active/resolved disjointness; revise closure doctrine so correction, regression evidence, and independent review authorize the ledger move and canonical exact-tree CI certifies the resulting zero-active-defect tree; add malformed, duplicate, overlap, unsafe-path, and valid-closure regressions.

**Current assessment and remaining actions:** Resolved records require exact fields, preserved facts, valid safe evidence and real reviewed ancestry, with active/resolved accounting. The final closure transaction is still pending.

**Implementation references:**

- `src/constructionsight/governance_contract_schema.py`: `_audit_resolved_defects` (line 370).
- `src/constructionsight/defect_closure_certification.py`: `audit_defect_closure` (line 220).

**Regression and integration references:**

- `tests/test_governance_contract_schema.py` (11 test functions in the passing starting suite).
- `tests/test_review_binding_certification.py` (14 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-DEFECT-FACTS-001`, `CS-MUT-DEFECT-ANCESTRY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-027 — P0 — partially corrected

**Original root cause:** The independent-review certifier requires only nonblank reviewer text inside a repository-controlled JSON artifact. An implementing author can therefore self-author an otherwise valid artifact, claim an arbitrary reviewer identity, and satisfy the mechanical review gate without a separately submitted GitHub review.

**Required resolution (unaltered ledger text):** Bind the review artifact to a real GitHub pull-request review ID and exact reviewed commit; require canonical pull-request CI to fetch that review from GitHub and verify APPROVED state, matching reviewer login, matching commit, a human User identity distinct from the PR author and repository owner, and aggregate the external-review result as a mandatory finalization gate; add positive and spoofing regressions while retaining repository certification as the missing-review blocker before an artifact exists.

**Current assessment and remaining actions:** Authenticated external-human review exists for that optional mode; authenticated owner acceptance is separate. ADR-0009 supersedes the original mandatory-human policy. No real owner acceptance or completed native review set has been supplied, and this session cannot author it for the owner.

**Implementation references:**

- `src/constructionsight/github_review_certification.py`: `verify_github_review_binding` (line 40).
- `src/constructionsight/owner_acceptance_certification.py`: `verify_github_owner_acceptance` (line 184).

**Regression and integration references:**

- `tests/test_github_review_certification.py` (12 test functions in the passing starting suite).
- `tests/test_owner_acceptance_certification.py` (7 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-OWNER-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-OWNER-IDENTITY-001`, `CS-MUT-ASSURANCE-OWNER-COMMIT-001`, `CS-MUT-ASSURANCE-OWNER-BODY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-028 — P0 — correction evidenced

**Original root cause:** Resolved-defect validation checks schema and evidence references but does not prove that the original active-defect facts are identical to those present in the reviewed commit, and resolution commits are not proven to exist in reviewed history.

**Required resolution (unaltered ledger text):** Bind closure records to the reviewed commit's complete active-defect ledger, preserve every original defect field exactly, require complete reviewed-ID accounting, and prove each resolution commit exists and is an ancestor of the reviewed implementation commit.

**Current assessment and remaining actions:** Closure compares original complete defect facts from reviewed Git history, preserves previous resolutions and verifies resolution-commit ancestry. Changed-fact, partial-accounting and nonexistent/unrelated-commit fixtures pass.

**Implementation references:**

- `src/constructionsight/defect_closure_certification.py`: `reviewed_active_defects_digest` (line 180), `audit_defect_closure` (line 220).

**Regression and integration references:**

- `tests/test_review_binding_certification.py` (14 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-DEFECT-FACTS-001`, `CS-MUT-DEFECT-ANCESTRY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-029 — P0 — correction evidenced

**Original root cause:** The bounded HTTP layer can authorize one URL path representation while the HTTP client transmits a different normalized representation, and ambiguous encoded path forms are not rejected consistently.

**Required resolution (unaltered ledger text):** Derive one canonical outbound URL, validate and authorize that exact representation, reject ambiguous encoded separators, dot segments, backslashes, fragments, user information, and noncanonical percent encodings, and transmit only the authorized representation.

**Current assessment and remaining actions:** The exact canonical wire URL is authorized before transport; ambiguous encodings, separators, dot segments, credentials and fragments are rejected by corresponding regressions.

**Implementation references:**

- `src/constructionsight/http_transport.py`: `_validate_outbound_request` (line 397), `_validate_scope` (line 315).

**Regression and integration references:**

- `tests/test_http_transport.py` (26 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-030 — P0 — correction evidenced

**Original root cause:** The CEQAnet persistence facade authorizes a caller-owned mutable write-plan object and later gives the same object to the effect boundary, permitting authorization and execution content to diverge.

**Required resolution (unaltered ledger text):** Create a detached canonical write-plan snapshot before authorization, validate and hash that snapshot, recheck its exact identity immediately before the effect, execute only the detached snapshot, and add nested and callback-time mutation regressions.

**Current assessment and remaining actions:** The facade detaches the write-plan snapshot and rechecks its material identity immediately before persistence. Nested and callback-time substitution witnesses pass.

**Implementation references:**

- `src/constructionsight/operator_services/ceqanet_persistence_service.py`: `AuthorizedPersistenceResult` (line 27), `_CanonicalWritePlanSnapshot` (line 35), `_require_plain_json` (line 44), `_canonical_write_plan_payload` (line 66), `_materialize_write_plan_snapshot` (line 82), `_write_plan_identity` (line 94).

**Regression and integration references:**

- `tests/test_ceqanet_persistence_operator_service.py` (7 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-PERSIST-SNAPSHOT-001`, `CS-MUT-PERSIST-RECHECK-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-031 — P0 — correction evidenced

**Original root cause:** The exact installed Python environment is verified before vulnerability tooling runs, but the vulnerability action installs additional distributions into the same interpreter before lint, type, test, mutation, and repository-certification gates execute.

**Required resolution (unaltered ledger text):** Run vulnerability tooling in an isolated job or interpreter and verify the supported interpreter's exact installed-distribution identity immediately before and after every executable quality-gate sequence.

**Current assessment and remaining actions:** The vulnerability collector runs in isolated jobs and the quality environment is checked before and after execution. Current CI shows exact-environment checks at both boundaries.

**Implementation references:**

- `src/constructionsight/dependency_certification.py`: `_audit_ci_environment_identity` (line 245).

**Regression and integration references:**

- `tests/test_dependency_certification.py` (18 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-DEPENDENCY-DRIFT-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-032 — P0 — correction evidenced

**Original root cause:** A production-visible CEQAnet compatibility client path enables redirect following even though the canonical network contract requires redirects to be denied at request time, and current regression coverage preserves the conflicting behavior.

**Required resolution (unaltered ledger text):** Deny redirects at request time on every production-visible CEQAnet path, remove or route the compatibility transport through the common bounded engine, and replace the conflicting regression with fail-closed redirect coverage.

**Current assessment and remaining actions:** Production-visible CEQAnet compatibility behavior routes through bounded redirect-denying execution. Redirect rejection witnesses pass; no redirect-following success contract is accepted.

**Implementation references:**

- `src/constructionsight/ceqanet_discovery_http.py`: `_validate_http_url` (line 33), `CeqanetDiscoveryResult` (line 38), `CeqanetLiveDiscovery` (line 113).
- `src/constructionsight/http_transport.py`: `execute_bounded_http` (line 461).

**Regression and integration references:**

- `tests/test_ceqanet_adapter.py` (7 test functions in the passing starting suite).
- `tests/test_http_transport.py` (26 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-033 — P0 — correction evidenced

**Original root cause:** Tracked symbolic links are not prohibited and several governance evidence, test, ADR, lock, and mutation references are accepted without proving their resolved targets remain inside the reviewed repository tree.

**Required resolution (unaltered ledger text):** Reject Git mode 120000 tracked symbolic links and require one centralized, symlink-resistant repository-containment check for every governance evidence, test, ADR, lock, review, and mutation reference.

**Current assessment and remaining actions:** Tracked symlinks and noncanonical/out-of-root governance references are rejected by the centralized repository-reference checks. Runtime handle/path races are a distinct unresolved CS-SR-054 boundary.

**Implementation references:**

- `src/constructionsight/repository_path_certification.py`: `resolve_repository_file` (line 12).
- `src/constructionsight/repository_certification.py`: `audit_repository` (line 524).

**Regression and integration references:**

- `tests/test_repository_path_certification.py` (4 test functions in the passing starting suite).
- `tests/test_repository_certification.py` (8 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CI-EXECUTABLE-001`, `CS-MUT-REPO-SYMLINK-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-034 — P0 — partially corrected

**Original root cause:** The static semantic-authorization audit trusts authorized-looking function names without resolving imported or aliased call targets and proving that canonical authorization occurs before every reachable effect.

**Required resolution (unaltered ledger text):** Replace naming-convention trust with a resolved interprocedural call graph from operator entry points to effect boundaries, prove authorization and preflight precede every reachable effect, and add spoofed-name, alias, indirect-call, branch-bypass, and effect-before-authorization regressions.

**Current assessment and remaining actions:** Resolved call graph and branch-phase analysis replace name trust and reject aliases, spoofing and direct effects in tested paths. Audit its complete operator/effect inventory against actual file publication and cross-actor mutations before declaring all reachable effects proven.

**Implementation references:**

- `src/constructionsight/semantic_authorization_certification.py`: `_Program` (line 133), `_AuthorizationGraphAudit` (line 353), `audit_semantic_authorization` (line 1110).

**Regression and integration references:**

- `tests/test_semantic_authorization_certification.py` (21 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-AUTH-EFFECT-TARGET-001`, `CS-MUT-CONSUME-CALLER-LEDGER-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-035 — P0 — correction evidenced

**Original root cause:** Exact network query scope remains partly prose because the bounded HTTP policy does not represent query authority and the CEQAnet listing planner accepts caller-supplied base search URLs.

**Required resolution (unaltered ledger text):** Represent exact query scope or canonical request identity in executable network policy, remove arbitrary base-URL injection from the CEQAnet planner, and reject any request whose host, path, query keys, query values, or canonical identity exceeds reviewed authority.

**Current assessment and remaining actions:** Complete request identity covers query keys and values, and canonical CEQAnet planning constrains the base search endpoint. Query drift and arbitrary scope fixtures pass.

**Implementation references:**

- `src/constructionsight/http_transport.py`: `_validate_scope` (line 315), `_validate_outbound_request` (line 397).
- `src/constructionsight/adapters/ceqanet_listing.py`: `CeqanetReadOnlyListingPlanner` (line 115).

**Regression and integration references:**

- `tests/test_http_transport.py` (26 test functions in the passing starting suite).
- `tests/test_ceqanet_listing_plan.py` (7 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-036 — P0 — correction evidenced

**Original root cause:** Exact-head CI run #1056 discovered newly published advisory PYSEC-2026-3721 against the locked pip 26.1.2 bootstrap distribution, so both supported environments now fail the mandatory zero-known-vulnerability gate.

**Required resolution (unaltered ledger text):** Upgrade both artifact-hashed environment locks and bootstrap doctrine to pip 26.2 or later using the reviewed exact wheel identity, rerun the full Python 3.11/3.12 vulnerability matrix, and retain zero-vulnerability evidence without an exception.

**Current assessment and remaining actions:** Both locks now bind the reviewed pip 26.2 identity; both exact-head vulnerability environments succeed without an exception. Recollect after any new candidate change.

**Implementation references:**

- `src/constructionsight/supply_chain.py`: `load_lock_entries` (line 93).
- `src/constructionsight/vulnerability_certification.py`: `certify` (line 196).

**Regression and integration references:**

- `tests/test_vulnerability_certification.py` (16 test functions in the passing starting suite).
- `tests/test_supply_chain.py` (18 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-VULNERABILITY-ACTIVE-001`, `CS-MUT-VULNERABILITY-DIGEST-001`, `CS-MUT-VULNERABILITY-RELEASE-001`, `CS-MUT-VULNERABILITY-MANIFEST-001`, `CS-MUT-VULNERABILITY-DUPLICATE-001`, `CS-MUT-VULNERABILITY-INVENTORY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-037 — P0 — correction evidenced

**Original root cause:** The bounded HTTP engine validates a canonical URL before passing it to an injected httpx.Client stream call, where client-level query parameters can be merged before transmission; the exact authorized identity can therefore diverge from the wire request despite CS-SR-029.

**Required resolution (unaltered ledger text):** Build one explicit request outside injected-client configuration, prevent client defaults and request hooks from changing its authorized URL or method before transmission, and add a regression proving client-level query configuration cannot cause an unauthorized request.

**Current assessment and remaining actions:** One explicit request is constructed outside client defaults; configured query mutation is refused in the test seam and unavailable as a production client-injection parameter.

**Implementation references:**

- `src/constructionsight/http_transport.py`: `_send_exact_request` (line 423), `_validate_outbound_request` (line 397).

**Regression and integration references:**

- `tests/test_http_transport.py` (26 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-038 — P0 — correction evidenced

**Original root cause:** Injected httpx.Client response hooks execute before the bounded HTTP engine inspects the response, so a hook can alter status, headers, body, or request evidence after transport and before policy classification.

**Required resolution (unaltered ledger text):** Reject configured response hooks before transport execution or replace client injection with a constrained transport-only boundary, and add a regression proving a response hook cannot transform an access-control response into accepted evidence.

**Current assessment and remaining actions:** Response hooks are rejected before transport in the deterministic seam; the production boundary owns the client. Hook-forged status/body/request fixtures pass.

**Implementation references:**

- `src/constructionsight/http_transport.py`: `_send_exact_request` (line 423).

**Regression and integration references:**

- `tests/test_http_transport.py` (26 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-039 — P0 — correction evidenced

**Original root cause:** The bounded HTTP engine creates its owned httpx.Client with the default trust_env=True and accepts preconfigured injected clients, so environment proxy routing, proxy credentials, CA trust, and client-certificate state can be introduced beneath exact URL and auth checks; auth=None does not neutralize transport-level environment or TLS credential configuration.

**Required resolution (unaltered ledger text):** Construct the production client with trust_env=False and explicit reviewed TLS settings, remove effect-capable preconfigured client injection from production-visible boundaries, isolate deterministic test transport behind a non-production boundary, and add regression and mutation coverage proving environment proxies, CA overrides, proxy credentials, and client certificates cannot alter production HTTP execution.

**Current assessment and remaining actions:** Owned clients disable ambient environment authority, use explicit TLS roots/hostname checking, and expose no production client injection. Proxy/CA/auth and source-boundary witnesses pass.

**Implementation references:**

- `src/constructionsight/http_transport.py`: `_build_http_client` (line 412), `_owned_tls_context` (line 219), `_PinnedHttpTransport` (line 168).

**Regression and integration references:**

- `tests/test_http_transport.py` (26 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-040 — P0 — correction evidenced

**Original root cause:** ArcGIS acquisition and rehearsal effect boundaries accept caller-configured httpx.Client instances and call Client.get or Client.stream, allowing client query defaults, authentication, hooks, redirect policy, environment proxy or TLS state, and custom transports to alter the request or response evidence beneath the reviewed plan; post-response history and endpoint checks occur only after effects, and the acquisition path does not reject redirect history.

**Required resolution (unaltered ledger text):** Route every production ArcGIS request through an environment-independent bounded transport that constructs and authorizes one exact canonical URL including its complete query, denies redirects before execution, rejects unauthorized authentication and hooks, removes effect-capable client injection from production-visible APIs, and adds query-default, auth, hook, redirect, proxy, TLS, and forged-evidence regressions plus focused mutants.

**Current assessment and remaining actions:** ArcGIS requests use bounded exact-query transport with owned TLS/environment state and redirect denial. Query-default, auth, hook, forged-evidence and legacy injection fixtures pass.

**Implementation references:**

- `src/constructionsight/parcel_source_acquisition_http.py`: `ParcelArcGISProbeExecutionError` (line 43), `ParcelArcGISHTTPPolicy` (line 48), `fetch_arcgis_capability_snapshot` (line 92), `execute_arcgis_probe_plan` (line 118), `_exact_request_url` (line 164), `_get_json_object` (line 174).
- `src/constructionsight/parcel_source_bulk_rehearsal_http.py`: `ParcelArcGISBulkHTTPError` (line 40), `ParcelArcGISBulkHTTPPolicy` (line 45), `ParcelArcGISBulkRehearsalPlan` (line 96), `build_arcgis_bulk_rehearsal_plan` (line 183), `HTTPParcelArcGISBulkRehearsalSource` (line 253), `_require_exact_body` (line 326).

**Regression and integration references:**

- `tests/test_parcel_source_acquisition_http.py` (6 test functions in the passing starting suite).
- `tests/test_parcel_source_bulk_rehearsal_http.py` (10 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ARCGIS-PROBE-CLIENT-INJECTION-001`, `CS-MUT-ARCGIS-BULK-CLIENT-INJECTION-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-041 — P0 — correction evidenced

**Original root cause:** The ArcGIS capability and probe transport calls Client.get and accesses response.content before comparing its length with max_response_bytes, so an untrusted response is fully materialized before the declared memory ceiling is enforced.

**Required resolution (unaltered ledger text):** Use the shared streamed bounded-response engine or an equivalent pre-read Content-Length check and incrementally bounded stream, stop at the first byte beyond the ceiling, retain no incomplete body as successful evidence, and add declared-length and chunked-oversize regressions and mutants.

**Current assessment and remaining actions:** Acquisition bodies stream through the shared bound before full materialization. Declared-length and incremental oversize witnesses pass; local artifact bounds are tracked under CS-SR-055.

**Implementation references:**

- `src/constructionsight/parcel_source_acquisition_http.py`: `ParcelArcGISProbeExecutionError` (line 43), `ParcelArcGISHTTPPolicy` (line 48), `fetch_arcgis_capability_snapshot` (line 92), `execute_arcgis_probe_plan` (line 118), `_exact_request_url` (line 164), `_get_json_object` (line 174).
- `src/constructionsight/http_transport.py`: `_read_bounded` (line 384).

**Regression and integration references:**

- `tests/test_parcel_source_acquisition_http.py` (6 test functions in the passing starting suite).
- `tests/test_http_transport.py` (26 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`, `CS-MUT-ARCGIS-PROBE-CLIENT-INJECTION-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-042 — P1 — correction evidenced

**Original root cause:** CS-NET-003 omits text/html from its approved CEQAnet CSV media types while the executable _ACCEPTED_MEDIA_TYPES allowlist includes text/html, so the machine-readable network contract and runtime acceptance boundary disagree.

**Required resolution (unaltered ledger text):** Remove HTML from the CSV transport success allowlist unless separately authorized by an exact reviewed policy, mechanically reconcile declared and executable media types, and add a regression proving a 200 HTML login, denial, or error page cannot enter the CSV evidence path as an accepted transport response.

**Current assessment and remaining actions:** CSV transport rejects HTML success bodies and the declared media policy is reconciled with the executable allowlist.

**Implementation references:**

- `src/constructionsight/ceqanet_csv_live_service.py`: `_policy` (line 40), `execute_ceqanet_csv_live_request` (line 63), `verify_ceqanet_csv_live_execution` (line 104), `_execution_from_observation` (line 209), `_inspect_complete_body` (line 246), `_build_execution` (line 267).
- `src/constructionsight/authority_certification.py`: `_audit_network` (line 40).

**Regression and integration references:**

- `tests/test_ceqanet_csv_live.py` (12 test functions in the passing starting suite).
- `tests/test_architecture_boundary_certification.py` (3 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CSV-IDENTITY-001`, `CS-MUT-NET-CSV-MEDIA-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-043 — P0 — partially corrected

**Original root cause:** Production-visible application and execution services can authorize an operation and then invoke caller-selected effect implementations such as executors, persisters, HTTP checkers, registries, adapters, or equivalent callbacks, so the implementation that performs the effect is not necessarily the implementation whose authority was reviewed.

**Required resolution (unaltered ledger text):** Remove caller-selected effect implementations from production-visible boundaries, route effects through ConstructionSight-owned concrete implementations, retain deterministic substitutes only behind test-only seams, preserve authorized success and failure semantics, and add regressions and mutants proving post-authorization implementation substitution is impossible.

**Current assessment and remaining actions:** Owned high-impact facades and signature-injection rejection exist. Lower-level rehearsal source/artifact-reader/store protocols remain production-visible; prove their reachability cannot substitute a protected implementation and inventory actual effects before closure.

**Implementation references:**

- `src/constructionsight/effect_consumption.py`: `_execute_owned_effect` (line 157).
- `src/constructionsight/semantic_authorization_certification.py`: `audit_semantic_authorization` (line 1110).

**Regression and integration references:**

- `tests/test_effect_consumption.py` (17 test functions in the passing starting suite).
- `tests/test_semantic_authorization_certification.py` (21 test functions in the passing starting suite).
- `tests/test_parcel_arcgis_operator_service.py` (5 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CONSUME-RESERVATION-001`, `CS-MUT-CONSUME-PROCESS-LOCAL-001`, `CS-MUT-CONSUME-TERMINAL-PERSIST-001`, `CS-MUT-CONSUME-CONTENT-001`, `CS-MUT-CONSUME-STALE-AUTH-001`, `CS-MUT-AUTH-EFFECT-TARGET-001`, `CS-MUT-CONSUME-CALLER-LEDGER-001`, `CS-MUT-CONSUME-REPLAY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-044 — P0 — partially corrected

**Original root cause:** Production-visible authorization and execution facades accept caller-controlled clocks or authorization timestamps, allowing an invented time to influence authorization validity, policy-date checks, date-scoped execution identity, and audit metadata.

**Required resolution (unaltered ledger text):** Move authoritative time acquisition behind a ConstructionSight-owned production clock boundary, retain deterministic clocks only for tests, bind all time-sensitive authorization and execution state to that trusted clock, and add regressions proving callers cannot backdate or forward-date production authority.

**Current assessment and remaining actions:** Protected effects acquire time internally and reject production clock injection. Audit lower-level execution APIs and distinguish deterministic offline creation/verification times from times capable of granting live authority before complete closure.

**Implementation references:**

- `src/constructionsight/effect_consumption.py`: `trusted_utc_now` (line 28), `_execute_owned_effect` (line 157).
- `src/constructionsight/local_operator_authorization.py`: `_trusted_authorization_time` (line 30), `LocalAuthorizationResult` (line 37), `_normalized_text` (line 62), `_canonical_values` (line 69), `resolve_local_operator_id` (line 76), `_emit_audit_event` (line 87).

**Regression and integration references:**

- `tests/test_effect_consumption.py` (17 test functions in the passing starting suite).
- `tests/test_local_operator_authorization.py` (5 test functions in the passing starting suite).
- `tests/test_semantic_authorization_certification.py` (21 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CONSUME-RESERVATION-001`, `CS-MUT-CONSUME-PROCESS-LOCAL-001`, `CS-MUT-CONSUME-TERMINAL-PERSIST-001`, `CS-MUT-CONSUME-CONTENT-001`, `CS-MUT-CONSUME-STALE-AUTH-001`, `CS-MUT-AUTH-BOOLEAN-001`, `CS-MUT-AUTH-UNICODE-001`, `CS-MUT-CONSUME-REPLAY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-045 — P0 — unresolved

**Original root cause:** Generic source preflight paths can construct an access profile whose login, captcha, robots, terms, paywall, and related restriction facts default to false without evidence that those facts were actually established, so an unknown restriction state can be treated as an affirmative lawful-access clearance.

**Required resolution (unaltered ledger text):** Represent unknown access facts explicitly, require evidence-backed or reviewed access facts before live authority is granted, prohibit default-false restriction construction from satisfying lawful preflight, and add regressions for unknown login, captcha, robots, terms, and paywall states.

**Current assessment and remaining actions:** Restriction fields still default False and an otherwise empty profile is ALLOWED. Introduce explicit unknown facts plus evidence/review binding, route generic preflights through them, and test every unknown restriction independently.

**Implementation references:**

- `src/constructionsight/legal.py`: `SourceAccessProfile` (line 32), `evaluate_access` (line 45).

**Regression and integration references:**

- `tests/test_access_policy.py` (3 test functions in the passing starting suite).
- `tests/test_source_readiness_authorization.py` (6 test functions in the passing starting suite).
- `tests/test_source_verifier.py` (3 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-046 — P0 — unresolved

**Original root cause:** Verification, confidence, manual-review claims, source independence, and similar epistemic states can be supplied as structurally valid caller assertions without mandatory binding to immutable evidence, evidence existence, reviewer identity, or derivation lineage.

**Required resolution (unaltered ledger text):** Make authoritative verification and confidence derived states rather than caller assertions, bind them to existing immutable evidence and reviewer or derivation provenance, validate evidence lineage and independence at the trust boundary, and add forged-provenance, missing-evidence, duplicate-lineage, and self-asserted-review regressions.

**Current assessment and remaining actions:** Verified/confidence values remain caller assertions, evidence references may be absent, and numeric confidence alone maps to VERIFIED. Derive authoritative states from retained evidence and reviewer/lineage provenance and reject missing, forged or duplicate evidence.

**Implementation references:**

- `src/constructionsight/provenance.py`: `Provenance` (line 12).
- `src/constructionsight/models.py`: `PublicSource` (line 90), `SourceVerificationResult` (line 117).
- `src/constructionsight/domain_types.py`: `confidence_band` (line 64).

**Regression and integration references:**

- `tests/test_intelligence_schemas.py` (9 test functions in the passing starting suite).
- `tests/test_parcel_assurance.py` (10 test functions in the passing starting suite).
- `tests/test_source_verifier.py` (3 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-047 — P1 — unresolved

**Original root cause:** Normalized values, fingerprints, candidate identifiers, and other derived semantic identities can be caller supplied or only partially content-bound instead of being recomputed and self-validating at authoritative model or persistence boundaries.

**Required resolution (unaltered ledger text):** Define canonical versioned derivation rules for every authoritative normalized value and derived identity, recompute and validate them from source content at trust boundaries, use collision-appropriate full digests where identity is security or evidence relevant, canonicalize symmetric identity pairs, and add forged-normalization, forged-fingerprint, reversed-pair, and stale-ID regressions.

**Current assessment and remaining actions:** Normalized values and fingerprint keys remain accepted inputs, and multiple IDs use truncated hashes. Implement versioned recomputation at authoritative boundaries, symmetric-pair canonicalization, and forged/stale-identity regressions.

**Implementation references:**

- `src/constructionsight/site_resolution_service.py`: `_identifier_from_fact` (line 112).
- `src/constructionsight/lead_dedupe_models.py`: `LeadFingerprint` (line 20).
- `src/constructionsight/contractor_identity_service.py`: `normalize_contractor_name` (line 22), `normalize_contractor_license` (line 29), `build_contractor_identity` (line 35), `resolve_contractor_identity` (line 86), `_license_signal` (line 120), `_score_identity` (line 142).

**Regression and integration references:**

- `tests/test_lead_dedupe_models.py` (5 test functions in the passing starting suite).
- `tests/test_contractor_identity_service.py` (7 test functions in the passing starting suite).
- `tests/test_site_resolution_service.py` (5 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-048 — P0 — unresolved

**Original root cause:** Opportunity, site-resolution, enrichment, and readiness logic can score or resolve evidence by signal presence while treating confidence as descriptive metadata, allowing inferred, ambiguous, conflicting, unverified, or zero-confidence inputs to contribute enough operational weight for actionable state.

**Required resolution (unaltered ledger text):** Make evidence eligibility and confidence part of operational scoring and resolution semantics, prohibit weak or conflicting evidence from independently producing actionable or canonical state, preserve explicit review states for uncertain evidence, and add low-confidence, conflicting, inferred, and missing-evidence readiness regressions.

**Current assessment and remaining actions:** Lead scores sum presence weights independently of confidence, and site resolution scores identifier kinds rather than evidence eligibility. Prevent low/zero-confidence, inferred, conflicting or missing evidence from independently producing actionable state.

**Implementation references:**

- `src/constructionsight/opportunity_enrichment_service.py`: `enrich_opportunity` (line 23), `_next_action` (line 171).
- `src/constructionsight/site_resolution_service.py`: `_score_candidate` (line 253).

**Regression and integration references:**

- `tests/test_opportunity_enrichment_service.py` (4 test functions in the passing starting suite).
- `tests/test_site_resolution_service.py` (5 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-049 — P0 — unresolved

**Original root cause:** A lead classified as duplicate REVIEW_NEEDED can retain a READY workflow state because duplicate uncertainty is recorded only as a limitation, and the workflow transition matrix permits READY to ACTIVE without proving duplicate review has been resolved.

**Required resolution (unaltered ledger text):** Make unresolved duplicate review a hard non-actionable workflow invariant, prohibit activation or outreach-relevant transitions while duplicate review remains unresolved, bind the transition check to durable duplicate-review state, and add READY, ACTIVE, and concurrent transition regressions.

**Current assessment and remaining actions:** REVIEW_NEEDED only appends a limitation; a high-score package can start READY and transition ACTIVE. Persist a typed duplicate-review gate and enforce it during creation and durable transitions, including competing updates.

**Implementation references:**

- `src/constructionsight/lead_workflow_service.py`: `_initial_status` (line 84), `transition_lead_workflow` (line 54).
- `src/constructionsight/lead_workflow_rules.py`: `validate_lead_workflow_transition` (line 60).

**Regression and integration references:**

- `tests/test_lead_workflow_service.py` (5 test functions in the passing starting suite).
- `tests/test_lead_workflow_transition_authorization.py` (6 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-050 — P0 — partially corrected

**Original root cause:** Lead workflow authorization checks an expected current state before mutation, but the durable state transition is performed through an ordinary read and upsert rather than a database compare-and-swap, so competing processes can authorize the same old state and race to overwrite one another.

**Required resolution (unaltered ledger text):** Bind the authorized expected state to the mutation with one database compare-and-swap or equivalent serializable transition primitive, reject stale writers, preserve append-only transition evidence, and add deterministic competing-writer and stale-authorization regressions.

**Current assessment and remaining actions:** The durable allowance prevents identical-operation replay, but workflow writes still read then upsert. Different actors or target transitions need one expected-state database CAS with immutable events; add distinct-operation competing-writer tests.

**Implementation references:**

- `src/constructionsight/lead_operator_service.py`: `transition_persisted_lead_workflow` (line 309).
- `src/constructionsight/storage/lead_workflow_store.py`: `store_lead_workflow_record` (line 206).
- `src/constructionsight/operator_services/lead_workflow_transition_service.py`: `apply_authorized_lead_workflow_transition` (line 34).

**Regression and integration references:**

- `tests/test_lead_workflow_transition_authorization.py` (6 test functions in the passing starting suite).
- `tests/test_lead_workflow_storage.py` (10 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-AUTH-LEAD-CONFIRM-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-051 — P1 — partially corrected

**Original root cause:** Several records that represent events, evidence, snapshots, or historical transitions use mutable upsert semantics or reusable stable IDs appropriate to current-state projections, allowing later writes to replace earlier historical state.

**Required resolution (unaltered ledger text):** Separate mutable current-state projections from append-only evidence, event, snapshot, and transition ledgers; require immutable transition-specific identity and exact idempotent replay for historical records; preserve supersession explicitly; and add replay, overwrite, and historical reconstruction regressions.

**Current assessment and remaining actions:** Result revisions reject conflicting replay, but permit snapshots/transitions, workflow events and enrichment reports overwrite existing rows. Separate projections from append-only history and test immutable replay, supersession and reconstruction across every historical family.

**Implementation references:**

- `src/constructionsight/storage/movement_identity_store.py`: `store_permit_snapshot` (line 21), `store_permit_transition` (line 54).
- `src/constructionsight/storage/lead_workflow_store.py`: `store_lead_workflow_event` (line 170), `store_opportunity_enrichment_report` (line 28), `store_result_ledger_record` (line 275).

**Regression and integration references:**

- `tests/test_movement_identity_storage.py` (6 test functions in the passing starting suite).
- `tests/test_lead_workflow_storage.py` (10 test functions in the passing starting suite).
- `tests/test_result_ledger_supersession.py` (3 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-052 — P1 — unresolved

**Original root cause:** Result ledger identity is derived from workflow, status, and revision without binding all semantically material outcome content, so materially different result records can share the same nominal ledger identifier.

**Required resolution (unaltered ledger text):** Define canonical result-ledger serialization and a full content digest covering every material outcome field, bind authority events to that digest, keep revision or head identity separate from content identity, and add regressions proving any material mutation changes the content identity.

**Current assessment and remaining actions:** Ledger ID binds workflow/status/revision rather than outcome content; changed amounts/reasons/date can retain the same ID. Add canonical full material-content identity, bind authority events, and keep revision identity separate.

**Implementation references:**

- `src/constructionsight/result_ledger_service.py`: `_ledger_id` (line 177), `_build_revision` (line 101).
- `src/constructionsight/result_ledger_models.py`: `ResultLedgerRecord` (line 60).

**Regression and integration references:**

- `tests/test_result_ledger_models.py` (5 test functions in the passing starting suite).
- `tests/test_result_ledger_supersession.py` (3 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-053 — P1 — unresolved

**Original root cause:** Result-share and royalty accounting validates decimal precision at input but performs and persists monetary arithmetic with binary floating-point values and implicit round(..., 2) semantics rather than a canonical monetary type and explicit rounding doctrine.

**Required resolution (unaltered ledger text):** Represent monetary values and rates with a fixed-decimal or integer-minor-unit domain, define an explicit rounding mode and scale, persist exact decimal values, migrate affected calculations without changing legitimate business semantics, and add boundary, half-cent, accumulation, and replay regressions.

**Current assessment and remaining actions:** Input precision checks use Decimal but arithmetic uses round(float * float, 2) and ORM columns remain Float. Define exact monetary representation and explicit rounding, migrate storage/serialization and verify half-cent, accumulation and replay behavior.

**Implementation references:**

- `src/constructionsight/result_ledger_service.py`: `_share_record` (line 159), `_share_id` (line 186).
- `src/constructionsight/result_ledger_models.py`: `ResultShareRecord` (line 31).
- `src/constructionsight/storage/lead_workflow_orm.py`: `ResultShareRecordRow` (line 256).

**Regression and integration references:**

- `tests/test_result_ledger_precision.py` (6 test functions in the passing starting suite).
- `tests/test_result_ledger_share_state.py` (1 test functions in the passing starting suite).
- `tests/test_result_ledger_service.py` (8 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-054 — P0 — partially corrected

**Original root cause:** Runtime evidence and artifact paths can be formed from manifest or artifact references and then resolved through ordinary filesystem operations without a uniform no-follow containment proof, permitting parent, absolute, or symlink-mediated reads or writes outside the intended evidence root.

**Required resolution (unaltered ledger text):** Centralize runtime evidence path resolution, require relative canonical names and resolved containment beneath the evidence root, reject symlink or reparse traversal at every component and final target, bind verified bytes to later use, and add absolute, parent, symlink, swap, and verify-use regressions.

**Current assessment and remaining actions:** Basename checks, final-component no-follow on supported systems and verified-byte binding exist for some CEQAnet paths. Parent components are reopened by pathname, ArcGIS stores still follow paths, and no-follow silently becomes zero where unavailable. Centralize handle-relative reads/publication, reject all symlink/reparse components, preserve verified-byte use and test parent/final swaps plus unsupported capabilities.

**Implementation references:**

- `src/constructionsight/ceqanet_operator_bundle_verify.py`: `_require_contained_bundle_file` (line 161), `_open_regular_bundle_file` (line 171).
- `src/constructionsight/parcel_source_bulk_rehearsal_artifacts.py`: `JSONFileParcelArcGISBulkArtifactStore` (line 122).
- `src/constructionsight/parcel_source_bulk_rehearsal_bundle.py`: `save_arcgis_bulk_rehearsal_proof_bundle` (line 174).

**Regression and integration references:**

- `tests/test_ceqanet_operator_bundle_verify.py` (13 test functions in the passing starting suite).
- `tests/test_ceqanet_operator_archive.py` (8 test functions in the passing starting suite).
- `tests/test_parcel_source_bulk_rehearsal.py` (13 test functions in the passing starting suite).
- `tests/test_parcel_source_bulk_rehearsal_bundle.py` (13 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-055 — P1 — partially corrected

**Original root cause:** Some externally controlled local or adapter work is bounded only after materialization or is not bounded at all, including whole-file intake, ZIP entry decompression, and adapter enumeration that calls list(...) before applying max_records.

**Required resolution (unaltered ledger text):** Apply byte, record, and decompression ceilings before full materialization, stream or incrementally consume bounded work, abort at the first unit beyond the reviewed ceiling, and add oversized-file, compression-ratio, infinite-generator, and max-record regressions.

**Current assessment and remaining actions:** Recent file, adapter, ZIP and proof bounds are present and tested. Several operator/evidence JSON loaders still call read_text before applying any bound; audit complete local intake/decompression/serialization paths and add pre-materialization, ratio, infinite-stream and exact-limit witnesses.

**Implementation references:**

- `src/constructionsight/intake_service.py`: `IntakeInspectionInput` (line 102), `inspect_lawful_input` (line 113), `inspect_lawful_file` (line 176), `detect_format_family` (line 202), `extract_material_facts` (line 301), `build_unmapped_fragments` (line 352).
- `src/constructionsight/adapters/runner.py`: `AdapterRunner` (line 24).
- `src/constructionsight/ceqanet_operator_archive_verify.py`: `CeqanetArchiveArtifactVerification` (line 33), `CeqanetOperatorArchiveVerification` (line 61), `verify_ceqanet_operator_archive` (line 134), `_require_bounded_archive_metadata` (line 196), `_bounded_member_chunks` (line 210), `_duplicate_filenames` (line 240).
- `src/constructionsight/parcel_source_bulk_rehearsal_artifacts.py`: `JSONFileParcelArcGISBulkArtifactStore` (line 122).

**Regression and integration references:**

- `tests/test_intake_service.py` (9 test functions in the passing starting suite).
- `tests/test_adapter_runner.py` (8 test functions in the passing starting suite).
- `tests/test_ceqanet_operator_archive_verify.py` (9 test functions in the passing starting suite).
- `tests/test_parcel_source_acquisition_bundle.py` (8 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-056 — P1 — unresolved

**Original root cause:** Database initialization relies on SQLAlchemy metadata create_all without a governed schema-version or migration mechanism, so existing databases can retain obsolete columns, constraints, or table shapes while current ORM models and certification assume a newer schema.

**Required resolution (unaltered ledger text):** Introduce a deterministic repository-native schema version and migration or fail-closed compatibility mechanism, verify the persisted schema before application effects, provide explicit upgrade provenance, and add old-schema, partial-upgrade, wrong-version, and fresh-database regressions.

**Current assessment and remaining actions:** Hardening initialization still calls metadata.create_all without schema version/compatibility verification. GUI docket checks cover only that workflow. Add a repository-wide migration or fail-closed compatibility mechanism before durable effects, with old/partial/wrong/fresh-schema tests and upgrade provenance.

**Implementation references:**

- `src/constructionsight/storage/database.py`: `initialize_database` (line 39).

**Regression and integration references:**

- `tests/test_domain_orm.py` (2 test functions in the passing starting suite).
- `tests/test_domain_store.py` (8 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-057 — P1 — partially corrected

**Original root cause:** Foundational site, permit, planning, and related domain models do not uniformly enforce physical and lifecycle invariants, allowing impossible coordinates, negative physical measurements, contradictory dates, or similarly invalid states into durable projections.

**Required resolution (unaltered ledger text):** Add the minimum domain-native validators required for physically and temporally valid state, explicitly define allowed unknown or partial states, reject contradictory lifecycle ordering at authoritative boundaries, and add boundary and chronology regressions without refactoring unrelated domain logic.

**Current assessment and remaining actions:** Some measurements have nonnegative constraints, but Site latitude/longitude/acreage are unbounded and permit/planning dates have no lifecycle ordering checks. Define legitimate partial states and add finite physical bounds plus unambiguous chronological invariants at authoritative boundaries.

**Implementation references:**

- `src/constructionsight/site_models.py`: `Site` (line 10).
- `src/constructionsight/permit_models.py`: `PermitRecord` (line 14).
- `src/constructionsight/planning_models.py`: `PlanningCaseRecord` (line 14).

**Regression and integration references:**

- `tests/test_site_models.py` (2 test functions in the passing starting suite).
- `tests/test_permit_models.py` (4 test functions in the passing starting suite).
- `tests/test_planning_models.py` (4 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-058 — P0 — partially corrected

**Original root cause:** Multi-artifact filesystem operations can durably write an audit or report artifact before the corresponding authoritative target is successfully committed, allowing durable evidence to claim an apply or mutation that never completed.

**Required resolution (unaltered ledger text):** Define one commit protocol for coupled filesystem artifacts, stage and fsync or equivalently prepare all outputs before authoritative replacement, publish success evidence only after the target commit succeeds, recover deterministically from partial failure, and add injected late-write, replacement, and crash-point regressions.

**Current assessment and remaining actions:** Individual artifact staging/fsync and ArcGIS create-only publication exist. Registry audit/backup/target operations have no shared crash-recoverable commit transaction; define authoritative commit and success-evidence ordering with late-write, replace and crash-point recovery tests.

**Implementation references:**

- `src/constructionsight/source_registry_update_plan_cli.py`: `source_registry_apply` (line 226), `_atomic_write_text` (line 71).
- `src/constructionsight/ceqanet_operator_bundle.py`: `_write_serialized_artifact` (line 169).
- `src/constructionsight/parcel_source_bulk_rehearsal_bundle.py`: `save_arcgis_bulk_rehearsal_proof_bundle` (line 174).

**Regression and integration references:**

- `tests/test_source_registry_update_plan.py` (14 test functions in the passing starting suite).
- `tests/test_ceqanet_operator_bundle.py` (10 test functions in the passing starting suite).
- `tests/test_parcel_source_bulk_rehearsal_bundle.py` (13 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-059 — P1 — partially corrected

**Original root cause:** Some frozen or content-addressed outer models contain mutable nested models or collections, so validated content can change after identity or digest construction without forcing a new identity.

**Required resolution (unaltered ledger text):** Make content-addressed evidence recursively immutable or defensively detached, use immutable collection types for digest-bound fields, prevent nested post-validation mutation, and add nested-list, nested-model, stale-digest, and copy-isolation regressions.

**Current assessment and remaining actions:** Several evidence models use frozen outer objects and tuples, while other digest-bound plans contain mutable nested dictionaries/models. Inventory the full content graph, freeze or defensively detach nested content, revalidate authoritative boundaries and test nested mutation/copy isolation.

**Implementation references:**

- `src/constructionsight/authorization_decision_models.py`: `AuthorizationReusePolicy` (line 21), `_json_value` (line 28), `authorization_digest` (line 40), `AuthorizationDecision` (line 52), `AuthorizationPreflight` (line 163).
- `src/constructionsight/parcel_source_bulk_rehearsal_bundle_models.py`: `ParcelArcGISBulkPortableArtifact` (line 32), `ParcelArcGISBulkRehearsalProofBundle` (line 84), `ParcelArcGISBulkRehearsalProofVerification` (line 240).
- `src/constructionsight/source_registry_update_plan_models.py`: `SourceRegistryUpdatePlanRow` (line 14), `SourceRegistryUpdatePlanReport` (line 41), `compute_source_registry_update_plan_digest` (line 79).

**Regression and integration references:**

- `tests/test_authorization_decision.py` (7 test functions in the passing starting suite).
- `tests/test_parcel_source_bulk_rehearsal_bundle.py` (13 test functions in the passing starting suite).
- `tests/test_source_registry_update_plan.py` (14 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-060 — P0 — partially corrected

**Original root cause:** Generic source-readiness and source-verification transports derive their allowed host and exact request authority from the same caller-controlled source URL they are meant to constrain, so canonical loopback, private, link-local, reserved, or otherwise internal destinations can self-authorize a bounded HTTP request.

**Required resolution (unaltered ledger text):** Derive executable source authority only from a separately governed source identity and public-egress policy; reject IP literals and special-use hostnames; validate every resolved address and alias as globally routable; prevent resolution-to-connect rebinding or enforce equivalent network egress controls; preserve exact request, redirect, credential, TLS, and response bounds; and add loopback, private, link-local, numeric-address, mixed-answer, CNAME, and rebinding regressions.

**Current assessment and remaining actions:** A separate source allowlist, globally routable answer checks and resolution-to-connect pinning exist with mixed-answer/numeric/rebinding fixtures. Complete alias-chain and cross-runtime integration evidence, and verify every generic production source path uses that authority boundary before closure.

**Implementation references:**

- `src/constructionsight/source_authority_rules.py`: `governed_source_url` (line 18).
- `src/constructionsight/http_transport.py`: `_resolve_public_authority` (line 237), `_PinnedNetworkBackend` (line 88), `_PinnedHttpTransport` (line 168).

**Regression and integration references:**

- `tests/test_http_transport.py` (26 test functions in the passing starting suite).
- `tests/test_source_readiness_authorization.py` (6 test functions in the passing starting suite).
- `tests/test_source_verifier.py` (3 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-NET-REDIRECT-001`, `CS-MUT-NET-SIZE-001`, `CS-MUT-NET-QUERY-AUTHORITY-001`, `CS-MUT-NET-CLIENT-INJECTION-001`, `CS-MUT-NET-AMBIENT-ENV-001`, `CS-MUT-NET-TLS-VERIFY-001`, `CS-MUT-NET-CLIENT-CERT-001`, `CS-MUT-NET-IP-LITERAL-001`, `CS-MUT-NET-PUBLIC-RESOLUTION-001`, `CS-MUT-NET-RESOLUTION-PIN-001`, `CS-MUT-NET-EXPLICIT-REQUEST-001`, `CS-MUT-NET-CLIENT-AUTH-001`, `CS-MUT-NET-REQUEST-HOOK-001`, `CS-MUT-NET-RESPONSE-HOOK-001`, `CS-MUT-NET-RESPONSE-REQUEST-IDENTITY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-061 — P0 — partially corrected

**Original root cause:** High-impact authorization and evidence-execution paths determine use or attempt availability from caller-selected, invocation-local, absent, or stale snapshot state and perform the effect without a ConstructionSight-owned atomic consumption reservation, allowing one logical authorization, UTC-date allowance, or recurring-run attempt identity to cause multiple effects.

**Required resolution (unaltered ledger text):** Introduce a ConstructionSight-owned consumption service that atomically reserves the exact decision or operation identity immediately before effect execution; use durable uniqueness or compare-and-swap for cross-process database, file, evidence-series, and recurring-run operations; remove production ledger and used-ID injection; bind reservation to exact scope, current state, trusted time, and the owned implementation; make permitted exact replay return the prior committed result without repeating effects; persist terminal success or failure; and add sequential, concurrent, restart, stale-series, duplicate-sequence, and failed-effect recovery regressions.

**Current assessment and remaining actions:** SQLite durable reservation, result replay and terminal/indeterminate failure handling are implemented. Registry reservation covers an in-memory calculation while CLI publication happens later; business state still lacks CAS and actor-scoped reservations need reconciliation with globally scoped date/attempt allowances. Complete these exact effect scopes and test distinct actors, changed destinations and recovery.

**Implementation references:**

- `src/constructionsight/effect_consumption.py`: `_execute_owned_effect` (line 157).
- `src/constructionsight/storage/effect_consumption_store.py`: `EffectConsumptionStore` (line 93).
- `src/constructionsight/operator_services/source_registry_service.py`: `apply_authorized_source_registry_update_plan` (line 178).

**Regression and integration references:**

- `tests/test_effect_consumption.py` (17 test functions in the passing starting suite).
- `tests/test_ceqanet_csv_evidence_series.py` (22 test functions in the passing starting suite).
- `tests/test_ceqanet_recurring_run_operator_service.py` (4 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CONSUME-RESERVATION-001`, `CS-MUT-CONSUME-PROCESS-LOCAL-001`, `CS-MUT-CONSUME-TERMINAL-FAILURE-001`, `CS-MUT-CONSUME-TERMINAL-PERSIST-001`, `CS-MUT-CONSUME-CONTENT-001`, `CS-MUT-CONSUME-STALE-AUTH-001`, `CS-MUT-CONSUME-REPLAY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-062 — P0 — correction evidenced

**Original root cause:** Native assurance permits reviewed_commit to be any ancestor of HEAD, while reviewed_tree_digest is verified only against the current assurance-covered index tree and is not recomputed from the reviewed commit. An assurance report can therefore bind analytical passes and quality evidence to an older commit while rebinding the digest to a newer non-finalization implementation tree.

**Required resolution (unaltered ledger text):** Compute the assurance-covered tree digest directly from reviewed_commit using canonical Git object identities and the same finalization exclusions; require it to equal reviewed_tree_digest and the current covered tree digest; preserve permitted post-review finalization paths; and add stale-reviewed-commit, covered-tree-change, allowed-finalization, and exact-tree regression coverage.

**Current assessment and remaining actions:** The reviewed commit's covered Git tree is recomputed and compared to both the report and current covered tree. Stale-ancestor/non-finalization drift and allowed-finalization fixtures pass.

**Implementation references:**

- `src/constructionsight/governance_certification.py`: `_assured_commit_tree_digest` (line 75), `_audit_assurance_reviewed_tree_binding` (line 122).

**Regression and integration references:**

- `tests/test_review_binding_certification.py` (14 test functions in the passing starting suite).
- `tests/test_assurance_reviewed_tree_binding.py` (4 test functions in the passing starting suite).

**Focused mutation references:** No directly mapped focused mutant was established for these implementation/test pairs. Add or reconcile meaningful witnesses where the resolution requires them.

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-063 — P0 — correction evidenced

**Original root cause:** Native assurance counts caller-authored completed_reviews values toward minimum context-isolated and deep-review thresholds, so one analytical pass and evidence artifact can claim multiple supposedly fresh contexts; the canonical test helper satisfies three deep reviews with one native-deep artifact.

**Required resolution (unaltered ledger text):** Require each context-isolated review to be a distinct pass ID and distinct evidence artifact with completed_reviews exactly 1; require at least five native pass records and at least three distinct deep_repository records, bind each to a unique execution or context identity, and add aggregation, duplicate-context, exact-count regression, and focused mutation coverage.

**Current assessment and remaining actions:** Each pass must have completed_reviews=1 with unique pass/context/artifact identities; at least five distinct passes and three deep passes are enforced and mutation-tested. No real five-pass campaign has yet been performed here.

**Implementation references:**

- `src/constructionsight/assurance_certification.py`: `_audit_passes` (line 665).

**Regression and integration references:**

- `tests/test_assurance_certification.py` (20 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-FRESH-CONTEXT-001`, `CS-MUT-ASSURANCE-DEEP-COUNT-001`, `CS-MUT-ASSURANCE-DEFERRED-CANDIDATE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-COVERAGE-GAP-001`, `CS-MUT-ASSURANCE-SURVIVING-MUTANT-001`, `CS-MUT-ASSURANCE-PASS-EVIDENCE-001`, `CS-MUT-ASSURANCE-GATE-EVIDENCE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-CONTEXT-AGGREGATION-001`, `CS-MUT-ASSURANCE-SOURCE-DIGEST-001`, `CS-MUT-ASSURANCE-SOURCE-COMMIT-001`, `CS-MUT-ASSURANCE-SOURCE-REUSE-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-064 — P0 — correction evidenced

**Original root cause:** Pass and quality-gate evidence treats source_artifact_sha256 as a syntax-only 64-hex assertion without a resolvable source artifact, so fabricated or stale raw-review and CI provenance, including all-zero hashes, can satisfy Native Maximum Assurance.

**Required resolution (unaltered ledger text):** Require every source artifact identity to resolve to immutable retained bytes or an externally authenticated CI artifact identity; verify SHA-256 against those bytes or identity and exact reviewed commit or run metadata; reject placeholders and unresolvable hashes; preserve safe containment and unique ownership; and add zero-hash, missing-source, digest-mismatch, cross-commit, reused-source regression, and focused mutation coverage.

**Current assessment and remaining actions:** Retained raw bytes, actual SHA-256, exact commit, unique ownership and semantic source agreement are enforced; missing, placeholder, reused, stale and tampered source regressions pass.

**Implementation references:**

- `src/constructionsight/assurance_certification.py`: `_source_artifact` (line 557).
- `src/constructionsight/assurance_source_certification.py`: `audit_assurance_source_semantics` (line 290).

**Regression and integration references:**

- `tests/test_assurance_certification.py` (20 test functions in the passing starting suite).
- `tests/test_assurance_source_certification.py` (6 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-FRESH-CONTEXT-001`, `CS-MUT-ASSURANCE-DEEP-COUNT-001`, `CS-MUT-ASSURANCE-DEFERRED-CANDIDATE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-COVERAGE-GAP-001`, `CS-MUT-ASSURANCE-SURVIVING-MUTANT-001`, `CS-MUT-ASSURANCE-PASS-EVIDENCE-001`, `CS-MUT-ASSURANCE-GATE-EVIDENCE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-CONTEXT-AGGREGATION-001`, `CS-MUT-ASSURANCE-SOURCE-DIGEST-001`, `CS-MUT-ASSURANCE-SOURCE-COMMIT-001`, `CS-MUT-ASSURANCE-SOURCE-REUSE-001`, `CS-MUT-ASSURANCE-SOURCE-SEMANTIC-PRODUCER-001`, `CS-MUT-ASSURANCE-SOURCE-SEMANTIC-PAYLOAD-001`, `CS-MUT-ASSURANCE-SOURCE-SEMANTIC-SHAPE-001`, `CS-MUT-ASSURANCE-QUALITY-SOURCE-WIRING-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-065 — P2 — partially corrected

**Original root cause:** Assurance provenance and mutation-overlay hardening introduced six overlong Python lines, an unsorted import block, and a nested conditional rejected by the mandatory Ruff rules. Exact-head CI 1146 on 7c302bc925884d5c6aa3d9fc0191e68672c2a37a reports eight Ruff errors and a failed lint outcome, so that candidate does not satisfy the Native Maximum Assurance quality baseline even though tests and focused mutants pass.

**Required resolution (unaltered ledger text):** Correct all eight Ruff violations without suppressions, rule changes, or weakened predicates; preserve behavior and mutation anchors; rerun the complete exact-head Python 3.11 and 3.12 matrix; and verify the retained raw Ruff output and actual gate outcomes rather than a continue-on-error step conclusion before making any clean-quality claim.

**Current assessment and remaining actions:** The specifically discovered eight lint errors are no longer reported. The required complete clean current matrix is not satisfied because CS-SR-075 introduces separate lint/preflight failures; retain a genuinely clean later exact-head run.

**Implementation references:**

- `src/constructionsight/assurance_certification.py`: `_nonblank` (line 227), `_positive_integer` (line 231), `_nonnegative_integer` (line 235), `_record` (line 239), `_exact_fields` (line 248), `_canonical_strings` (line 271).
- `src/constructionsight/assurance_source_certification.py`: `_nonblank` (line 50), `_positive_int` (line 54), `_record` (line 60), `_read_json_reference` (line 70), `_audit_source_payload` (line 94), `_audit_analytical_sources` (line 141).

**Regression and integration references:**

- `tests/test_assurance_certification.py` (20 test functions in the passing starting suite).
- `tests/test_assurance_source_certification.py` (6 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-FRESH-CONTEXT-001`, `CS-MUT-ASSURANCE-DEEP-COUNT-001`, `CS-MUT-ASSURANCE-DEFERRED-CANDIDATE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-COVERAGE-GAP-001`, `CS-MUT-ASSURANCE-SURVIVING-MUTANT-001`, `CS-MUT-ASSURANCE-PASS-EVIDENCE-001`, `CS-MUT-ASSURANCE-GATE-EVIDENCE-001`, `CS-MUT-ASSURANCE-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-CONTEXT-AGGREGATION-001`, `CS-MUT-ASSURANCE-SOURCE-DIGEST-001`, `CS-MUT-ASSURANCE-SOURCE-COMMIT-001`, `CS-MUT-ASSURANCE-SOURCE-REUSE-001`, `CS-MUT-ASSURANCE-SOURCE-SEMANTIC-PRODUCER-001`, `CS-MUT-ASSURANCE-SOURCE-SEMANTIC-PAYLOAD-001`, `CS-MUT-ASSURANCE-SOURCE-SEMANTIC-SHAPE-001`, `CS-MUT-ASSURANCE-QUALITY-SOURCE-WIRING-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-066 — P0 — correction evidenced

**Original root cause:** Native Maximum Assurance requires explicit owner acceptance, but the canonical report currently treats owner_acceptance as a repository-controlled Boolean with nonblank owner and review_method text; no externally authenticated owner action binds the decision to the exact frozen commit, reviewed tree, and complete material assurance evidence set, so a committer or automation capable of writing permitted finalization artifacts can self-assert owner acceptance.

**Required resolution (unaltered ledger text):** Bind owner acceptance to the repository owner's real GitHub User identity, exact pull-request review ID, exact reviewed commit and tree, and a deterministic SHA-256 digest of all material assurance claims; have canonical CI re-fetch and verify the owner review with read-only GitHub authority; require exact acceptance text, COMMENTED state, OWNER association, and human User identity; keep owner acceptance distinct from independent-human review; and add spoofed-owner, stale-commit, changed-evidence, wrong-body/state, wiring, and focused-mutation regressions.

**Current assessment and remaining actions:** Owner identity, exact GitHub review, state, association, commit/tree/material digest and acceptance text are verified through read-only authority. Fixtures verify rejection semantics; actual owner acceptance remains an explicit final user action.

**Implementation references:**

- `src/constructionsight/owner_acceptance_certification.py`: `assurance_evidence_digest` (line 83), `expected_acceptance_body` (line 105), `verify_github_owner_acceptance` (line 184).

**Regression and integration references:**

- `tests/test_owner_acceptance_certification.py` (7 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-OWNER-EVIDENCE-DIGEST-001`, `CS-MUT-ASSURANCE-OWNER-IDENTITY-001`, `CS-MUT-ASSURANCE-OWNER-COMMIT-001`, `CS-MUT-ASSURANCE-OWNER-BODY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-067 — P2 — partially corrected

**Original root cause:** The semantic CI-permission regression helper creates its workflow directory without exist_ok=True, but test_scalar_or_duplicate_permissions_fail_closed rewrites the same temporary workflow twice. Exact-head CI #1153 on 99081b3cd2f4d6dc1916f13c36e09ecda76ac7e1 therefore fails full pytest on both Python 3.11 and 3.12 with FileExistsError despite the production permission certifier, focused mutations, preflight, and repository certification otherwise behaving as intended.

**Required resolution (unaltered ledger text):** Make the test workflow helper idempotently create its parent directory, rerun the complete exact-head Python 3.11 and 3.12 matrix, require all 1323 tests to pass, preserve 92/92 focused mutation results, and confirm canonical repository certification contains only ASSURANCE-001 plus the active-defect blockers.

**Current assessment and remaining actions:** The idempotent workflow fixture passes and the full current suites exceed the original 1323-test checkpoint. All current quality gates still need a clean exact-head rerun after CS-SR-075; no historical count is reused as new evidence.

**Implementation references:**

- `src/constructionsight/ci_permissions_certification.py`: `top_level_permissions` (line 33), `audit_ci_permissions` (line 62).

**Regression and integration references:**

- `tests/test_ci_permissions_certification.py` (4 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-CI-PERMISSIONS-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-068 — P1 — partially corrected

**Original root cause:** Canonical CI pins third-party GitHub Action source commits, but the pinned checkout, setup-python, and upload-artifact commits declare Node 20 while current GitHub-hosted runners forcibly execute those bundles under Node 24. The immutable source SHA therefore no longer fixes the interpreter semantics actually executing in CI, and the workflow lacks a native binding from Action identity to a reviewed runtime class.

**Required resolution (unaltered ledger text):** Review and pin Node-24-native checkout, setup-python, and upload-artifact releases by immutable commit; preserve existing least-privilege and quality semantics; machine-certify the exact Action repositories, commits, occurrence counts, and reviewed runtime annotations; retain the composite pip-audit identity; rerun the complete exact-head matrix; and require the Node-20 forced-runtime warning to disappear before assurance freeze.

**Current assessment and remaining actions:** Reviewed Node-24-native Action SHAs, runtime annotations and occurrence counts are enforced. Raw current jobs execute these pins; complete required clean-matrix qualification remains blocked by unrelated current gate failures.

**Implementation references:**

- `src/constructionsight/ci_action_certification.py`: `audit_ci_actions` (line 72).

**Regression and integration references:**

- `tests/test_ci_action_certification.py` (5 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-CI-ACTION-COMMIT-001`, `CS-MUT-ASSURANCE-CI-ACTION-REVIEW-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-069 — P1 — correction evidenced

**Original root cause:** The immutable pypa/gh-action-pip-audit composite source does not pin the scanner implementation it executes: its requirements allow resolver-selected pip-audit and transitive versions, so the mandatory vulnerability gate can change without a ConstructionSight tree or Action-SHA change.

**Required resolution (unaltered ledger text):** Remove the resolver-selected vulnerability-scanner bootstrap; use a repository-owned deterministic vulnerability certifier with explicit fail-closed advisory provenance or a fully artifact-hashed exact scanner environment; preserve isolated zero-known-vulnerability enforcement and retained evidence; add negative network, schema, advisory, and mutation coverage; and rerun the complete supported-runtime matrix.

**Current assessment and remaining actions:** Repository-owned bounded collection plus deterministic fail-closed release-specific advisory verification replaces resolver-selected scanner bootstrap. Both supported current-head isolated audits succeed; malformed, unavailable, stale and advisory-present fixtures and mutants pass.

**Implementation references:**

- `src/constructionsight/vulnerability_certification.py`: `certify` (line 196).
- `src/constructionsight/vulnerability_ci_certification.py`: `audit_vulnerability_job` (line 112).

**Regression and integration references:**

- `tests/test_vulnerability_certification.py` (16 test functions in the passing starting suite).
- `tests/test_vulnerability_collection.py` (9 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-VULNERABILITY-ACTIVE-001`, `CS-MUT-VULNERABILITY-DIGEST-001`, `CS-MUT-VULNERABILITY-RELEASE-001`, `CS-MUT-VULNERABILITY-MANIFEST-001`, `CS-MUT-VULNERABILITY-DUPLICATE-001`, `CS-MUT-VULNERABILITY-HTTP-STATUS-001`, `CS-MUT-VULNERABILITY-SIZE-001`, `CS-MUT-VULNERABILITY-INVENTORY-001`, `CS-MUT-VULNERABILITY-CI-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-070 — P2 — partially corrected

**Original root cause:** CS-SR-068 Action-provenance hardening introduced two overlong expressions in src/constructionsight/ci_action_certification.py. Retained CI #1155 evidence reports Ruff E501, so exact head 7fe708e1ea49044b2b847a9624da5c80c765a679 is not a clean-quality or assurance-freeze candidate.

**Required resolution (unaltered ledger text):** Split both overlong expressions without suppression, rule changes, or weakened predicates; preserve Action identity/runtime semantics and mutation anchors; rerun the complete Python 3.11 and 3.12 matrix; and verify retained raw Ruff output is clean before assurance freeze.

**Current assessment and remaining actions:** The two original overlong Action expressions are corrected. The required complete clean current matrix remains blocked by separate CS-SR-075 issues; retain actual later Ruff output and gate outcomes.

**Implementation references:**

- `src/constructionsight/ci_action_certification.py`: `audit_ci_actions` (line 72).

**Regression and integration references:**

- `tests/test_ci_action_certification.py` (5 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-ASSURANCE-CI-ACTION-COMMIT-001`, `CS-MUT-ASSURANCE-CI-ACTION-REVIEW-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-071 — P0 — partially corrected

**Original root cause:** The isolated vulnerability job invokes three noninteractive Bash steps without step-local BASH_ENV neutralization. A workflow, job, runner, or inherited environment can therefore point BASH_ENV at attacker-controlled startup content that Bash evaluates before the canonically certified step body, allowing the execution semantics to diverge from the text the vulnerability CI certifier binds.

**Required resolution (unaltered ledger text):** Set BASH_ENV to /dev/null at each security-critical vulnerability Bash step, bind all occurrences and their placement into the exact vulnerability-job execution contract, add missing-or-weakened neutralizer regressions and focused mutation coverage, rerun the complete exact-head supported-runtime matrix, and retain CS-SR-071 as active until exact-tree Native Maximum Assurance legitimately closes the reviewed defect history.

**Current assessment and remaining actions:** All three security-critical BASH_ENV neutralizers and their placement are bound with negative and mutation witnesses. Full clean supported-runtime qualification remains pending alongside current lint/preflight repair.

**Implementation references:**

- `src/constructionsight/vulnerability_ci_certification.py`: `audit_vulnerability_job` (line 112).

**Regression and integration references:**

- `tests/test_vulnerability_ci_startup.py` (7 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-VULNERABILITY-BASH-ENV-SYMLINK-PLACEMENT-001`, `CS-MUT-VULNERABILITY-BASH-ENV-AUDIT-PLACEMENT-001`, `CS-MUT-VULNERABILITY-BASH-ENV-ENFORCEMENT-PLACEMENT-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-072 — P0 — partially corrected

**Original root cause:** The canonical CI workflow launches noninteractive Bash without suppressing inherited shell options and exported functions. SHELLOPTS=noexec skips a failing script and exits successfully even with BASH_ENV=/dev/null; an imported test function can also turn failed enforcement into success. A workflow-level noexec setting outside the literal vulnerability-job block passes the complete existing structural preflight, and quality-job shells remain exposed to inherited startup hooks.

**Required resolution (unaltered ledger text):** Use an explicit reviewed Bash executable and startup-isolated launch flags for every canonical CI run step, preserving errexit and pipefail; bind all workflow bytes including global settings and quality-job controls into structural and final certification; preserve the existing BASH_ENV neutralizers and vulnerability-job contract; add real inherited-option, exported-function, startup-hook, command-resolution, and failure-propagation regressions plus digest and integration mutation witnesses; rerun the complete supported-runtime matrix; and retain the defect until exact-tree Native Maximum Assurance closure.

**Current assessment and remaining actions:** Every canonical shell uses the reviewed startup-isolated flags; complete workflow bytes are bound and inherited-option/function/hook witnesses pass. Full clean-matrix and Native Maximum Assurance requirements remain unmet.

**Implementation references:**

- `src/constructionsight/ci_execution_certification.py`: `audit_ci_execution` (line 128).

**Regression and integration references:**

- `tests/test_ci_execution_certification.py` (13 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CI-EXECUTION-DIGEST-001`, `CS-MUT-CI-PRE-GATE-PROJECT-INSTALL-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-073 — P0 — partially corrected

**Original root cause:** The quality job installed the pull-request candidate with pip install --no-deps --no-build-isolation -e . before the structural and assurance gates. Because the candidate controls its PEP 517 build backend and build configuration, repository-controlled build code could execute before those gates and mutate runner command files or the checkout, allowing later gate execution to diverge from the reviewed workflow while the whole-workflow digest itself remained unchanged.

**Required resolution (unaltered ledger text):** Remove all candidate project installation and build execution from the pre-gate quality bootstrap; install only the exact hash-locked third-party environment; execute canonical source through a reviewed PYTHONPATH binding; certify the dependency-only install block and prohibit additional project-install commands independently of the workflow digest; verify source-project identity without invoking a build backend and reject installed-project shadowing; add regression and mutation coverage; rerun both supported runtimes; and retain CS-SR-073 as active until exact-tree Native Maximum Assurance legitimately closes reviewed defect history.

**Current assessment and remaining actions:** Candidate installation/build execution is removed before gates; only locked third-party dependencies install, source identity is verified and project shadowing fails. Full clean supported-runtime matrix and final assurance remain pending.

**Implementation references:**

- `src/constructionsight/ci_execution_certification.py`: `_bootstrap_findings` (line 69).
- `src/constructionsight/supply_chain.py`: `_source_project` (line 182).

**Regression and integration references:**

- `tests/test_ci_execution_certification.py` (13 test functions in the passing starting suite).
- `tests/test_supply_chain_source_tree.py` (4 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CI-EXECUTION-DIGEST-001`, `CS-MUT-CI-PRE-GATE-PROJECT-INSTALL-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-074 — P0 — partially corrected

**Original root cause:** Both supported artifact-hashed dependency locks retained AnyIO 4.9.0 when exact-head CI newly detected active GHSA-5p39-cfhj-2xmp (CVE-2026-64847) and GHSA-82r6-8w77-94w6 (CVE-2026-63374); their distinct public disclosure dates are not inferred from the CI detection date. The canonical 2026-09-20 exact-head CI vulnerability audits identified both as active and failed, invalidating reliance on the older no-active-advisory checkpoint. Exposure of affected AnyIO code paths within ConstructionSight has not been independently established.

**Required resolution (unaltered ledger text):** Retain independent source evidence for both advisories and the reviewed fixed AnyIO release; pin exact PyPI-published universal wheel identity and SHA-256 consistently for Python 3.11 and 3.12; validate strict hash-locked installation, dependency compatibility, network/TLS behavior, full tests and independent fresh vulnerability collection at an exact new head; propagate the fix to stacked GUI and hardening trees; keep this defect active until Native Maximum Assurance, reviewed closure and authenticated owner acceptance legitimately succeed.

**Current assessment and remaining actions:** Both locks carry AnyIO 4.14.2 with the same wheel hash and both branches have fresh successful vulnerability jobs. Full current quality matrices still fail CS-SR-075; preserve advisory/release provenance and rerun complete qualification after fixes.

**Implementation references:**

- `src/constructionsight/supply_chain.py`: `load_lock_entries` (line 93).
- `src/constructionsight/vulnerability_certification.py`: `certify` (line 196).

**Regression and integration references:**

- `tests/test_supply_chain_source_tree.py` (4 test functions in the passing starting suite).
- `tests/test_vulnerability_certification.py` (16 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-VULNERABILITY-ACTIVE-001`, `CS-MUT-VULNERABILITY-DIGEST-001`, `CS-MUT-VULNERABILITY-RELEASE-001`, `CS-MUT-VULNERABILITY-MANIFEST-001`, `CS-MUT-VULNERABILITY-DUPLICATE-001`, `CS-MUT-VULNERABILITY-INVENTORY-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## CS-SR-075 — P1 — unresolved

**Original root cause:** Recent artifact and consumption corrections introduced nine mandatory Ruff violations on hardening, ten on the stacked GUI, and a prohibited conditional pytest skip decorator. Raw exact-head CI logs for hardening 1a8f1b1e38e9f7ab11adcf629400fb4123c8ddf8 and GUI a3392b8c1b7f44eb0c3c536b737bdae1420c646f show lint failure and CERT-SUPPRESS-001 even though continue-on-error step conclusions say success; native structural preflight fails independently of active-defect and missing-assurance blockers.

**Required resolution (unaltered ledger text):** Correct the five shared import-order violations and the additional GUI source-candidate docket import-order violation, nested context-manager violation, and three loop-variable capture violations; replace the platform skip with meaningful platform-capability coverage without suppressing a required check; preserve runtime assertions and certification rules; rerun exact-head Python 3.11 and 3.12 lint, tests, mutations and structural preflight on both stacked branches; retain actual command outcomes and keep the finding active until legitimate Native Maximum Assurance closure.

**Current assessment and remaining actions:** Newly confirmed on both current heads: nine Ruff errors and forbidden skipif cause actual lint/preflight failures. Correct code/test construction without suppressions, replace capability skipping with meaningful rejection testing, and rerun both exact-head matrices.

**Implementation references:**

- `src/constructionsight/ceqanet_csv_service.py`: `build_ceqanet_csv_export_request` (line 86), `parse_ceqanet_csv_export_url` (line 115), `inspect_ceqanet_csv_bytes` (line 158), `_decode_csv_body` (line 279), `_validate_sch_number` (line 294), `_validate_content_type` (line 299).
- `src/constructionsight/ceqanet_operator_archive.py`: `CeqanetOperatorArchive` (line 31), `build_ceqanet_operator_archive` (line 64), `_manifest_filenames` (line 151), `_verified_content` (line 172), `_write_zip` (line 198), `_metadata_object` (line 256).
- `src/constructionsight/storage/effect_consumption_store.py`: `EffectConsumptionError` (line 21), `EffectAlreadyConsumedError` (line 25), `EffectReplayConflictError` (line 29), `EffectOutcomeUnavailableError` (line 33), `_require_wal_mode` (line 68), `EffectConsumptionStore` (line 93).

**Regression and integration references:**

- `tests/test_ceqanet_operator_bundle_verify.py` (13 test functions in the passing starting suite).
- `tests/test_effect_consumption.py` (17 test functions in the passing starting suite).
- `tests/test_parcel_source_acquisition_bundle.py` (8 test functions in the passing starting suite).

**Focused mutation references:** `CS-MUT-CONSUME-TERMINAL-FAILURE-001`

**Legitimate closure:** Fresh five-pass exact-candidate Native Maximum Assurance, full clean supported-runtime matrix, complete finding/coverage reconciliation, authentic owner acceptance, and reviewed-history closure under ADR-0008/0009. No current entry is authorized for ledger closure.

## Starting CI interpretation correction

The initial reconciliation described nine lint errors on each branch. Integrated GUI verification and a second inspection of both retained GUI job logs identified ten: the nine shared errors plus an existing import-order violation in `source_candidate_docket_service.py`. CS-SR-075 includes this additional correction. This does not close any defect or change the original 74-entry inventory.
