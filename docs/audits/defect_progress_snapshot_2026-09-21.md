# Defect progress snapshot — 2026-09-21

## Evidence boundary

This **non-certifying, fix-only progress snapshot** is a classification of the 75 records in `governance/active_defects.toml`, not an amendment to that ledger or an authorization to close any entry. The 74 original entries retain the individually documented assessment in [the starting reconciliation](fix_only_reconciliation_2026-09-21.md); **those 74 were assessed at an earlier head**, and have **not** each received a new per-defect complete-tree review at this snapshot's head. Later correction work recorded in [the execution record](fix_only_progress_2026-09-21.md) materially advanced CS-SR-054/055, but explicitly leaves them partial. CS-SR-075 is updated from the starting reconciliation's `unresolved` to `correction evidenced (narrow corrective scope)`: lint/test-suppression corrections passed exact-head CI at previous checkpoints and the latest observed hardening CI below. This classification is **not** final Native Maximum Assurance or defect closure. Reopen/adjust any category if new adverse evidence is found.

Reference head: `62d747172892adb9be24a4d331428080edd91ad2` (PR #117, draft). The snapshot is written as a new documentation commit, so the reference head's CI results **must not be represented as qualification of the new documentation commit**. No source code or quality gate is modified by this document.

## Separate implementation signal from formal defect closure

| Provisional implementation assessment | Records | Percentage of 75 | Meaning |
|---|---:|---:|---|
| Correction mechanism evidenced at the documented checkpoint | 42 | 56.0% | Mapped correction and regression evidence exist; not proven complete-tree-safe at final candidate |
| Partially corrected; specific correction or verification work remains | 25 | 33.3% | Substantial or limited work is present but a known gap remains |
| Unresolved at the documented checkpoint | 8 | 10.7% | No sufficient correction was established in the existing individual reconciliation |
| Formally closed | 0 | 0.0% | No completed assurance, owner acceptance, or reviewed-history closure |

These are **percentages of records by status, not percentages of engineering effort remaining**. Defects differ substantially in scope and the baseline is not a fresh per-defect audit of the latest source tree.

## Latest observed exact-head CI, not release qualification

At `62d747172892adb9be24a4d331428080edd91ad2`, GitHub Actions run [35633520373](https://github.com/TruSudo/Construction-Sight/actions/runs/35633520373) completed. Actual Python 3.11 and 3.12 hardening job logs each report 1,854 passing tests, 142/142 focused mutants killed, successful lint/typing/preflight/installed-environment checks and successful isolated vulnerability audit jobs. The aggregate quality jobs fail on release certification: **75 active-defect findings plus one missing assurance report**. Passing tests do not establish a per-defect closure or Windows native qualification. The 1,958 GUI tests are local diagnostics at the previous output batch; this snapshot does not claim their new exact-head qualification.

## Per-record provisional status

The underlying detailed reconciliation identifies each issue's original root cause, required remedy, mapped implementation, regression evidence and remaining work. The table below provides the **current status label only**, incorporating CS-SR-075's observed correction and preserving the other 74 baseline classifications pending focused re-review.

| Defect | Severity | Area | Provisional implementation status |
|---|---|---|---|
| CS-SR-001 | P1 | architecture | correction evidenced |
| CS-SR-002 | P1 | capability-traceability | correction evidenced |
| CS-SR-003 | P1 | supply-chain | correction evidenced |
| CS-SR-004 | P1 | network-resilience | correction evidenced |
| CS-SR-005 | P1 | authorization | correction evidenced |
| CS-SR-006 | P1 | certification | correction evidenced |
| CS-SR-007 | P2 | independent-review | partially corrected |
| CS-SR-008 | P0 | supply-chain-vulnerability | correction evidenced |
| CS-SR-009 | P1 | dependency-certification | correction evidenced |
| CS-SR-010 | P1 | adversarial-testing | correction evidenced |
| CS-SR-011 | P0 | exact-head-ci | partially corrected |
| CS-SR-012 | P1 | installed-environment-inventory | correction evidenced |
| CS-SR-013 | P1 | sbom-provenance | correction evidenced |
| CS-SR-014 | P1 | dependency-policy-traceability | correction evidenced |
| CS-SR-015 | P1 | governance-schema | correction evidenced |
| CS-SR-016 | P1 | cross-contract-traceability | correction evidenced |
| CS-SR-017 | P1 | adversarial-contract-doctrine | correction evidenced |
| CS-SR-018 | P0 | network-authorization-architecture | partially corrected |
| CS-SR-019 | P0 | authorization-construction | correction evidenced |
| CS-SR-020 | P0 | bounded-response-enforcement | correction evidenced |
| CS-SR-021 | P0 | intent-implementation-divergence | correction evidenced |
| CS-SR-022 | P0 | atomic-persistence | correction evidenced |
| CS-SR-023 | P0 | synchronization-integrity | partially corrected |
| CS-SR-024 | P0 | independent-review-binding | correction evidenced |
| CS-SR-025 | P0 | independent-review-worktree-binding | correction evidenced |
| CS-SR-026 | P0 | defect-closure-ledger-integrity | correction evidenced |
| CS-SR-027 | P0 | independent-review-identity-authenticity | partially corrected |
| CS-SR-028 | P0 | defect-closure-fact-integrity | correction evidenced |
| CS-SR-029 | P0 | http-url-canonicalization | correction evidenced |
| CS-SR-030 | P0 | persistence-authorization-toctou | correction evidenced |
| CS-SR-031 | P0 | ci-environment-identity | correction evidenced |
| CS-SR-032 | P0 | ceqanet-redirect-doctrine | correction evidenced |
| CS-SR-033 | P0 | repository-evidence-containment | correction evidenced |
| CS-SR-034 | P0 | semantic-authorization-proof | partially corrected |
| CS-SR-035 | P0 | network-query-authority | correction evidenced |
| CS-SR-036 | P0 | supply-chain-vulnerability | correction evidenced |
| CS-SR-037 | P0 | http-exact-request-identity | correction evidenced |
| CS-SR-038 | P0 | http-response-evidence-integrity | correction evidenced |
| CS-SR-039 | P0 | http-environment-and-transport-authority | correction evidenced |
| CS-SR-040 | P0 | arcgis-exact-request-and-evidence-integrity | correction evidenced |
| CS-SR-041 | P0 | arcgis-bounded-response-enforcement | correction evidenced |
| CS-SR-042 | P1 | network-media-type-contract-drift | correction evidenced |
| CS-SR-043 | P0 | effect-implementation-authority | partially corrected |
| CS-SR-044 | P0 | trusted-time-authority | partially corrected |
| CS-SR-045 | P0 | lawful-access-fact-authority | unresolved |
| CS-SR-046 | P0 | epistemic-provenance-authority | unresolved |
| CS-SR-047 | P1 | derived-identity-integrity | unresolved |
| CS-SR-048 | P0 | operational-confidence-gating | unresolved |
| CS-SR-049 | P0 | duplicate-review-gate | unresolved |
| CS-SR-050 | P0 | business-transition-concurrency | partially corrected |
| CS-SR-051 | P1 | historical-ledger-separation | partially corrected |
| CS-SR-052 | P1 | result-ledger-content-identity | unresolved |
| CS-SR-053 | P1 | financial-decimal-integrity | unresolved |
| CS-SR-054 | P0 | runtime-evidence-containment | partially corrected |
| CS-SR-055 | P1 | pre-materialization-resource-bounds | partially corrected |
| CS-SR-056 | P1 | database-schema-evolution | unresolved |
| CS-SR-057 | P1 | foundational-domain-invariants | partially corrected |
| CS-SR-058 | P0 | cross-artifact-commit-atomicity | partially corrected |
| CS-SR-059 | P1 | deep-content-immutability | partially corrected |
| CS-SR-060 | P0 | public-source-egress-authority | partially corrected |
| CS-SR-061 | P0 | effect-consumption-atomicity | partially corrected |
| CS-SR-062 | P0 | assurance-reviewed-tree-binding | correction evidenced |
| CS-SR-063 | P0 | assurance-context-isolation-integrity | correction evidenced |
| CS-SR-064 | P0 | assurance-source-provenance-integrity | correction evidenced |
| CS-SR-065 | P2 | assurance-quality-gate-compliance | partially corrected |
| CS-SR-066 | P0 | assurance-owner-acceptance-authenticity | correction evidenced |
| CS-SR-067 | P2 | assurance-quality-gate-compliance | partially corrected |
| CS-SR-068 | P1 | supply-chain-action-runtime-provenance | partially corrected |
| CS-SR-069 | P1 | supply-chain-vulnerability-toolchain-reproducibility | correction evidenced |
| CS-SR-070 | P2 | assurance-quality-gate-compliance | partially corrected |
| CS-SR-071 | P0 | assurance-execution-integrity | partially corrected |
| CS-SR-072 | P0 | ci-inherited-execution-controls | partially corrected |
| CS-SR-073 | P0 | ci-pre-gate-build-execution | partially corrected |
| CS-SR-074 | P0 | supply-chain-newly-disclosed-anyio-advisories | partially corrected |
| CS-SR-075 | P1 | artifact-remediation-quality-regression | correction evidenced (narrow corrective scope; awaiting assurance) |

## Active correction sequence — no expansion of product scope

1. **CS-SR-054 / CS-SR-055:** Complete the remaining evidence/output path and pre-materialization-bound inventories. On supported platforms, verify each call site uses contained no-follow handles and the reviewed byte/record limits. Preserve fail-closed behavior on unsupported native primitives; do not claim Windows success without native evidence.
2. **CS-SR-058:** Correct coupled registry apply, audit, backup and target ordering. Stage and durably prepare outputs, commit the authoritative target before publishing a success claim, define conflict/error semantics and deterministic recovery/orphan cleanup. Test late failure, parent swap, racing writer and interrupted publication. A single-artifact atomic publisher is not a multi-artifact transaction.
3. **CS-SR-061 / CS-SR-050 / CS-SR-049:** Couple exact-scope authorization consumption to authoritative effects and durable workflow compare-and-swap. Block unresolved duplicate-review leads from becoming actionable even under competing transitions.
4. **CS-SR-045 through 048, 052/053/056 and other remaining partial items:** Address evidence-backed lawful-access facts, provenance, derived identity, operational confidence, result content identity, exact monetary representation and persisted schema compatibility; use the individual reconciliation's negative-case requirements.
5. **Only after implementation gaps are eliminated:** Fresh exact-candidate tests, supported-environment CI, mutation/coverage review, five genuine isolated analytical passes, candidate reconciliation, owner acceptance and governed ledger closure. Keep PR #117 draft; no merge to main without explicit owner authorization.

Do not interpret a reclassification as a suppressed finding. The authoritative defect ledger remains unchanged, with all 75 records active.
