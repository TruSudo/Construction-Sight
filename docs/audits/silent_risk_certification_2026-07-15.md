# ConstructionSight Silent-Risk Certification Dossier

## Status

**Not certified. The August 13 adversarial review failed and invalidated candidate `4cc3ce763354ea91ef8c4bed28c3ce0b531379c3`. Thirty-five active defects now block any review, closure, readiness, or merge claim.**

This dossier records the correction and regression evidence for the active silent-risk defect ledger. It is an evidence record, not a substitute for independent review, and it does not itself authorize any defect to move from `governance/active_defects.toml` to `governance/resolved_defects.toml`.

The implementation tree reviewed on August 13 was:

```text
4cc3ce763354ea91ef8c4bed28c3ce0b531379c3
```

That tree is retained for provenance only. It is no longer a valid review or certification candidate. The failed review is recorded in `docs/audits/adversarial_review_2026-08-13.md`, and its eight P0 findings are registered as `CS-SR-028` through `CS-SR-035`.

This document was intentionally one of the four post-review finalization artifacts excluded from the reviewed-tree digest. That prior finalization allowance is no longer operative because the reviewed candidate failed. Any correction to a review-covered path requires a new exact candidate and a fresh adversarial review.

The only tracked paths permitted to change after independent review without invalidating the reviewed-tree digest are:

```text
governance/reviews/independent_review.json
governance/active_defects.toml
governance/resolved_defects.toml
docs/audits/silent_risk_certification_2026-07-15.md
```

Any corrected candidate requires a new independent review of the complete corrected tree.

## Historical pre-review exact-head evidence

The evidence below proves the ordinary gates that passed before the August 13 adversarial review. It does not certify the invalidated candidate and does not cover `CS-SR-028` through `CS-SR-035`.

Canonical GitHub Actions run **#1050** (`31673225260`) explicitly checked out and verified exact SHA:

```text
4cc3ce763354ea91ef8c4bed28c3ce0b531379c3
```

on both supported Python runtimes.

### Python 3.11

- exact checkout identity: passed
- exact locked-environment / installed-distribution verification: passed
- dependency integrity: passed
- deterministic SBOM: passed
- vulnerability audit: **no known vulnerabilities**
- Ruff: passed
- strict mypy: passed across **244 source files**
- compilation: passed
- warning-strict pytest: **1,122 / 1,122 passed**
- focused mutation certification: **13 / 13 mutants killed**
- adapter contract audit: passed
- source adapter coverage audit: passed
- external GitHub review stage: correctly remained pending because no independent-review artifact exists
- diff hygiene: passed
- retained artifact: `certification-py311`
- artifact ID: `9170525766`
- artifact ZIP SHA-256: `ee29ece7df358d4a8b65fda0e3201427e9874a342d4826f907ed9c5ce7acc1a6`
- artifact expiration reported by GitHub: `2026-08-20T06:18:07Z`

### Python 3.12

- exact checkout identity: passed
- exact locked-environment / installed-distribution verification: passed
- dependency integrity: passed
- deterministic SBOM: passed
- vulnerability audit: **no known vulnerabilities**
- Ruff: passed
- strict mypy: passed across **244 source files**
- compilation: passed
- warning-strict pytest: **1,122 / 1,122 passed**
- focused mutation certification: **13 / 13 mutants killed**
- adapter contract audit: passed
- source adapter coverage audit: passed
- external GitHub review stage: correctly remained pending because no independent-review artifact exists
- diff hygiene: passed
- retained artifact: `certification-py312`
- artifact ID: `9170536643`
- artifact ZIP SHA-256: `f8b97b1cfa9dcd4b67c53bbccad018a6fa67092098e927768309c8b90211ce14`
- artifact expiration reported by GitHub: `2026-08-20T06:18:36Z`

### Canonical repository-certification result

The retained repository-certification JSON from **both** runtime artifacts agrees exactly in substance:

- repository scan findings: **0**
- tracked files: **602**
- source Python files: **244**
- test Python files: **203**
- governance findings: **28 exactly**
- active-defect findings: **27**, one for each `CS-SR-001` through `CS-SR-027`
- other findings: **1**, `REVIEW-001`, because `governance/reviews/independent_review.json` does not yet exist
- architecture findings beyond the active ledger: **0**
- capability findings beyond the active ledger: **0**
- dependency/supply-chain findings beyond the active ledger: **0**
- network findings beyond the active ledger: **0**
- authorization findings beyond the active ledger: **0**
- governance-shape / traceability / adversarial-contract findings beyond the active ledger: **0**
- tracked-tree findings beyond the active ledger: **0**

At that historical checkpoint, the aggregate CI jobs remained red **by design** because all 27 then-known defects stayed active and `REVIEW-001` remained. The later failed review added eight implementation defects; the current blocker set is therefore 35 active defects plus the still-missing independent-review artifact.

## Closure doctrine

Defect closure is a two-stage transaction.

### Stage 1 — authorize the ledger move

A defect may move from active to resolved only after:

1. the stated root cause has been corrected;
2. focused regression evidence exists;
3. the corrected review-covered tree has received legitimate independent adversarial review;
4. the independent review has no unresolved findings affecting that defect or the certified tree; and
5. the resolved entry satisfies the strict evidence schema enforced by `governance_contract_schema.py`.

### Stage 2 — certify the resulting tree

After all reviewed defects have moved to the resolved ledger and the active ledger is empty, canonical exact-head CI must pass on Python 3.11 and Python 3.12 with:

- a valid independent-review artifact;
- successful external GitHub review revalidation;
- zero repository-certification findings;
- every executable quality gate successful; and
- retained final certification evidence.

Only that second stage permits the hardening effort or PR #117 to be represented as certified.

## Resolved-defect evidence contract

Every future `governance/resolved_defects.toml` entry must preserve the original active-defect facts and add exactly the enforced closure evidence, including:

- `resolution_summary`
- `resolution_commit`
- `evidence_paths`
- `regression_tests`
- `review_artifact`
- `reviewed_tree_digest`

The certifier rejects malformed or duplicate IDs, active/resolved overlap, invalid commit provenance, blank closure prose, unsafe/missing evidence paths, non-test regression paths, repository-relative symlink escape, missing/noncanonical review evidence, and reviewed-tree digest disagreement.

## Defect evidence matrix

All 35 defects remain active. The evidence below establishes the prior implementation/regression claims for `CS-SR-001` through `CS-SR-027`; the failed review proved those claims were incomplete at the system boundary. `CS-SR-028` through `CS-SR-035` have no accepted correction or regression evidence and must be remediated before a new candidate is frozen.

### CS-SR-001 — Architecture

**Root issue:** no strict machine-readable layer/capability-acquisition contract across the production tree.

**Correction evidence:**

- `governance/architecture_contract.toml`
- `src/constructionsight/architecture_certification.py`
- `src/constructionsight/architecture_boundary_certification.py`
- explicit layer permissions, module-cycle prohibition, and narrow ADR-backed expiring exceptions

**Regression evidence:**

- `tests/test_architecture_boundary_certification.py`
- #1050 produced no architecture finding beyond `CS-SR-001` remaining deliberately active

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-002 — Capability traceability

**Root issue:** capability maturity, modules, tests, doctrine, authority, and entry conditions were not mechanically reconciled.

**Correction evidence:**

- `governance/capability_contract.toml`
- `src/constructionsight/traceability_certification.py`
- exact module ownership and bidirectional capability-reference reconciliation

**Regression evidence:**

- `tests/test_governance_link_certification.py`
- `tests/test_governance_certification.py`
- #1050 produced no capability/traceability finding beyond the active ledger

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-003 — Supply-chain reproducibility

**Root issue:** open-ended dependency versions, resolver-selected CI environments, and mutable Action tags.

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
- #1050 exact lock verification, dependency integrity, deterministic SBOM, and vulnerability audit passed on both runtimes

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-004 — Network resilience inventory

**Root issue:** network paths were locally hardened but not governed by one complete approved-transport/policy inventory.

**Correction evidence:**

- `governance/network_contract.toml`
- `src/constructionsight/http_transport.py`
- `src/constructionsight/http_transport_models.py`
- architecture contract confines approved transport modules

**Regression evidence:**

- `tests/test_http_transport.py`
- `tests/test_semantic_authorization_certification.py`
- source-specific CEQAnet/ArcGIS transport regressions
- #1050 produced no extra network finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-005 — Repository-wide authorization contract

**Root issue:** feature-specific guards did not amount to a repository-wide scope-bound authorization model.

**Correction evidence:**

- `governance/authorization_contract.toml`
- `src/constructionsight/authorization_decision.py`
- `src/constructionsight/authorization_decision_models.py`
- operation-specific application/operator services and single-use preflight semantics

**Regression evidence:**

- `tests/test_authorization_decision.py`
- `tests/test_semantic_authorization_certification.py`
- operation-specific authorization tests registered in the adversarial matrix
- #1050 produced no extra authorization finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-006 — Canonical certification breadth

**Root issue:** canonical certification omitted major architecture, dependency, authorization, test, Action-pin, and review doctrine.

**Correction evidence:**

- `src/constructionsight/repository_certification_v2.py`
- `src/constructionsight/governance_certification.py`
- `src/constructionsight/governance_certification_core.py`
- architecture, dependency, authority, traceability, adversarial, and governance-shape certifiers

**Regression evidence:**

- `tests/test_repository_certification.py`
- `tests/test_governance_certification.py`
- `tests/test_governance_contract_schema.py`
- #1050 canonical audit reduced to the deliberate 27 active defects plus `REVIEW-001`

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-007 — Independent adversarial review doctrine

**Root issue:** high-risk change review had no mandatory structured, exact-tree, unresolved-finding gate.

**Correction evidence:**

- `docs/adr/ADR-0005-certification-doctrine.md`
- `src/constructionsight/authority_certification.py`
- certification is stricter than high-risk-only selection: the certified tree cannot pass without independent review at all

**Regression evidence:**

- `tests/test_review_binding_certification.py`
- #1050 correctly reports `REVIEW-001` while review is absent

**State:** implementation/regression controls present; the actual independent review is still pending.

### CS-SR-008 — Known dependency vulnerabilities

**Root issue:** the first exact environment audit found known vulnerabilities in several locked packages.

**Correction evidence:**

- reviewed fixed exact versions are represented in the supported locks and dependency governance

**Regression evidence:**

- #1050 vulnerability audit reported **no known vulnerabilities** under Python 3.11 and Python 3.12
- exact installed-environment verification passed on both runtimes

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-009 — Logical lock-row parsing

**Root issue:** physical-line parsing could misclassify backslash-continued hash rows.

**Correction evidence:**

- canonical logical-row parsing shared by dependency certification and supply-chain operations

**Regression evidence:**

- `tests/test_dependency_certification.py`
- `tests/test_supply_chain.py`
- #1050 lock verification/SBOM passed for both exact locks

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-010 — Mutation certification absent from CI

**Root issue:** focused mutation certification existed but was not enforced in the Python CI matrix.

**Correction evidence:**

- `.github/workflows/ci.yml` executes mutation certification in each runtime and includes it in aggregate enforcement

**Regression evidence:**

- `tests/test_mutation_detection.py`
- #1050: **13 / 13 mutants killed** on both Python versions

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-011 — Exact-head CI evidence

**Root issue:** prior hardening heads lacked canonical CI evidence tied to the actual branch SHA.

**Correction evidence:**

- `.github/workflows/ci.yml` explicitly checks out `${{ github.event.pull_request.head.sha || github.sha }}`
- mandatory checkout identity compares `git rev-parse HEAD` to the expected event SHA

**Regression evidence:**

- `tests/test_ci_exact_head_contract.py`
- #1050 verified exact SHA `4cc3ce763354ea91ef8c4bed28c3ce0b531379c3` on both runtimes

**State:** implementation-candidate exact-head evidence present; final post-review exact-head certification pending.

### CS-SR-012 — Installed-environment completeness

**Root issue:** undeclared or duplicate installed distributions and project-identity mismatches could remain outside certified inventory.

**Correction evidence:**

- exact project/bootstrap distribution policy in dependency governance
- `src/constructionsight/supply_chain.py` rejects unexpected/duplicate/malformed installed metadata

**Regression evidence:**

- `tests/test_supply_chain.py`
- #1050 installed-distribution verification passed on both runtimes

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-013 — SBOM provenance

**Root issue:** SBOM omitted artifact hashes/root identity guarantees and could use multiple inventory snapshots.

**Correction evidence:**

- deterministic SBOM implementation in `src/constructionsight/supply_chain.py`
- governed artifact identities and application root component

**Regression evidence:**

- `tests/test_supply_chain.py`
- #1050 deterministic SBOM passed on both runtimes

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-014 — Dependency-policy traceability

**Root issue:** dependency registry/policy validation could silently accept duplicate identities, stale policy, unsafe paths, or CI-policy divergence.

**Correction evidence:**

- strict dependency contract and fail-closed governance-shape/cross-lock validation
- canonical CI command requirements and immutable Action pins

**Regression evidence:**

- `tests/test_dependency_certification.py`
- `tests/test_governance_contract_schema.py`
- `tests/test_supply_chain.py`
- #1050 produced no extra dependency-policy finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-015 — Governance schema integrity

**Root issue:** unknown/misspelled governance fields and omitted governance surfaces could remain inert.

**Correction evidence:**

- `src/constructionsight/governance_contract_schema.py`
- canonical loading of architecture, capability, dependency, network, authorization, adversarial-test, mutation, active/resolved defect, overlap, and vulnerability-exception governance

**Regression evidence:**

- `tests/test_governance_contract_schema.py`
- #1050 produced no extra governance-shape finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-016 — Cross-contract traceability

**Root issue:** governance references were independently parsed rather than bidirectionally reconciled.

**Correction evidence:**

- `src/constructionsight/governance_link_certification.py`
- exact capability/policy/operation/dependency/adversarial reference reconciliation

**Regression evidence:**

- `tests/test_governance_link_certification.py`
- #1050 produced no extra cross-contract finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-017 — Adversarial-test contract doctrine

**Root issue:** adversarial matrices could contract categories, reference unsafe/missing tests, or contain malformed/empty doctrine.

**Correction evidence:**

- `governance/adversarial_test_contract.toml`
- `src/constructionsight/adversarial_contract_certification.py`

**Regression evidence:**

- `tests/test_adversarial_contract_certification.py`
- current matrix is canonical/sorted and includes review-binding, resolved-ledger, and external-review authenticity regressions
- #1050 produced no extra adversarial-contract finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-018 — CLI network/authorization bypass

**Root issue:** live CLI paths could import transport directly and treat bare Boolean confirmation as operative authority.

**Correction evidence:**

- architecture contract prohibits CLI-to-transport imports
- operation-specific services under `src/constructionsight/operator_services/`
- scope-bound decisions/preflights govern live and mutating operations

**Regression evidence:**

- `tests/test_semantic_authorization_certification.py`
- operation-specific authorization suites
- #1050 produced no CLI-to-transport or semantic-authorization finding beyond the active ledger

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-019 — Authorization construction defect

**Root issue:** placeholder all-zero digest identities were validated before real decision/preflight digests were constructed.

**Correction evidence:**

- `src/constructionsight/authorization_decision.py`
- `src/constructionsight/authorization_decision_models.py`

**Regression evidence:**

- `tests/test_authorization_decision.py`
- downstream operation-specific decision/preflight tests

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-020 — Bounded-response enforcement

**Root issue:** CEQAnet paths could follow redirects or materialize complete bodies before enforcing declared ceilings.

**Correction evidence:**

- streamed bounded transport in `src/constructionsight/http_transport.py`
- production CEQAnet/source-verification transports use fail-closed bounded behavior

**Regression evidence:**

- `tests/test_http_transport.py`
- `tests/test_ceqanet_listing_executor.py`
- `tests/test_ceqanet_csv_live.py`
- oversize/redirect/terminal-failure regressions

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-021 — CEQAnet intent/implementation divergence

**Root issue:** listing service/CLI/executor/model generations diverged and direct CLI construction bypassed the intended architecture.

**Correction evidence:**

- `src/constructionsight/ceqanet_listing_service.py`
- `src/constructionsight/adapters/ceqanet_listing_executor.py`
- `src/constructionsight/ceqanet_listing_execute_cli.py`
- canonical one-attempt listing doctrine and service/CLI alignment

**Regression evidence:**

- `tests/test_ceqanet_listing_service.py`
- `tests/test_ceqanet_listing_executor.py`
- `tests/test_ceqanet_listing_execute_cli.py`
- #1050 full import/runtime suite passed

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-022 — Atomic CEQAnet persistence

**Root issue:** partial commits could coexist with failed/skipped operations and a bare Boolean could act as write authority.

**Correction evidence:**

- `src/constructionsight/ceqanet_persistence_execute.py`
- `src/constructionsight/operator_services/ceqanet_persistence_service.py`
- complete-plan prevalidation, one transaction, rollback, exact plan/destination authorization

**Regression evidence:**

- `tests/test_ceqanet_persistence_execute.py`
- `tests/test_ceqanet_persistence_operator_service.py`
- `tests/test_ceqanet_persistence_execute_cli.py`

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-023 — Synchronization integrity

**Root issue:** sequential hardening commits allowed tests, application functions, architecture classification, governance inventories, and PR metadata to drift.

**Correction evidence:**

- pure domain/application ownership was reconciled
- test imports and CLI/application calls align with committed code
- architecture/capability/adversarial/defect/status inventories were synchronized
- at run #1050, PR #117 metadata pointed to the then-frozen candidate and evidence; the August 13 failed-review disposition now supersedes that target

**Regression evidence:**

- #1050 architecture/capability certification produced no extra findings
- **1,122 / 1,122 tests** passed on both runtimes
- exact-head checkout proven on both runtimes

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-024 — Independent-review topology binding

**Root issue:** `HEAD^` ancestry made review validity depend on GitHub synthetic-merge topology rather than reviewed content.

**Correction evidence:**

- `src/constructionsight/authority_certification.py` uses a deterministic review-covered index-tree digest
- reviewed commit remains provenance while content equality is topology-independent
- only four explicit finalization paths are excluded

**Regression evidence:**

- `tests/test_review_binding_certification.py`
- synthetic-merge equivalence, allowed finalization, and committed-tree tamper regressions

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-025 — Independent-review worktree binding

**Root issue:** index-based review digest could be computed while the reviewer inspected or executed non-permitted staged, unstaged, or untracked content not represented by the digest.

**Correction evidence:**

- `_assert_review_worktree_clean()` in `src/constructionsight/authority_certification.py`
- reviewed-tree digest fails closed on dirty review-covered paths while preserving the four finalization exclusions

**Regression evidence:**

- `tests/test_review_binding_certification.py`
- explicit unstaged-change rejection
- explicit staged-change rejection
- explicit untracked-file rejection
- permitted-finalization-path dirty state remains allowed and digest-stable
- #1050 produced no extra review-binding finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-026 — Defect-closure ledger integrity

**Root issue:** resolved defects lacked an exact evidence schema or active/resolved disjointness, and the original closure wording created a certification circular dependency.

**Correction evidence:**

- strict `_audit_resolved_defects()` in `src/constructionsight/governance_contract_schema.py`
- exact resolved-entry fields and commit provenance
- safe, existing, unique, sorted evidence/test paths
- path resolution must remain contained inside the repository; symlink escape is rejected
- canonical independent-review artifact and matching reviewed-tree digest required
- duplicate resolved IDs and active/resolved overlap rejected
- `governance/resolved_defects.toml` documents the non-circular two-stage closure doctrine

**Regression evidence:**

- `tests/test_governance_contract_schema.py`
- valid closure fixture
- malformed/unsafe evidence fixture
- duplicate/active-overlap fixture
- symlink-escape fixture
- canonical review-digest mismatch fixture
- #1050 produced no `GOV-RESOLVED-*` finding

**State:** correction/regression present; independent review/final certification pending.

### CS-SR-027 — Independent-review identity authenticity

**Root issue:** repository-controlled JSON could claim an arbitrary nonblank reviewer identity without proving that a separate reviewer actually submitted an approval.

**Correction evidence:**

- `src/constructionsight/github_review_certification.py`
- review artifact binds reviewer as `github:<login>#<review-id>`
- `.github/workflows/ci.yml` has read-only `pull-requests` permission for review revalidation only
- when a review artifact exists, CI fetches the exact GitHub PR review object and requires:
  - exact review ID
  - state `APPROVED`
  - matching reviewer login
  - reviewer type `User`
  - reviewer different from PR author
  - reviewer different from repository owner
  - review `commit_id` equal to artifact `reviewed_commit`
- a repository-controlled JSON artifact alone can no longer satisfy the external-review gate

**Regression evidence:**

- `tests/test_github_review_certification.py`
- `tests/test_ci_exact_head_contract.py`
- positive binding case
- malformed reviewer binding cases
- PR-author self-review rejection
- repository-owner self-review rejection
- non-approved review rejection
- review-ID mismatch rejection
- reviewer-login mismatch rejection
- bot identity rejection
- commit mismatch rejection
- #1050 correctly leaves external-review verification in pending state while the artifact is absent and preserves `REVIEW-001` as the canonical blocker

**State:** correction/regression present; **actual separate human GitHub approval remains pending**; final certification pending.

### CS-SR-028 — Defect-closure fact integrity

**Root issue:** closure validation does not bind resolved entries to the complete original defect facts at the reviewed commit and does not prove resolution-commit ancestry.

**Review evidence:** `AR-001` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** preserve every reviewed defect field exactly, require complete reviewed-ID accounting, and prove every resolution commit exists and is an ancestor of the reviewed implementation commit.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

### CS-SR-029 — HTTP URL canonicalization

**Root issue:** the URL representation authorized by the bounded HTTP layer can differ from the representation normalized and transmitted by the client.

**Review evidence:** `AR-002` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** canonicalize once, reject ambiguous URL forms, validate and authorize the exact canonical representation, and transmit only that representation.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

### CS-SR-030 — Persistence authorization TOCTOU

**Root issue:** CEQAnet persistence authorizes and later executes the same caller-owned mutable plan object.

**Review evidence:** `AR-003` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** authorize a detached canonical snapshot, recheck its identity immediately before the effect, execute only that snapshot, and cover nested and callback-time mutation.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

### CS-SR-031 — CI environment identity

**Root issue:** vulnerability tooling installs additional packages into the interpreter after exact installed-environment verification and before executable quality gates.

**Review evidence:** `AR-004` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** isolate vulnerability tooling and verify the supported interpreter immediately before and after the complete executable gate sequence.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

### CS-SR-032 — CEQAnet redirect doctrine

**Root issue:** a production-visible compatibility client enables redirect following even though the network contract requires denial at request time.

**Review evidence:** `AR-005` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** deny redirects on every production-visible path, remove or constrain the alternate transport, and replace the regression that currently preserves redirect following.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

### CS-SR-033 — Repository evidence containment

**Root issue:** tracked symbolic links and several governance references can escape uniform proof of containment within the reviewed repository tree.

**Review evidence:** `AR-006` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** reject Git mode `120000` and apply one symlink-resistant repository-containment primitive to every evidence, test, ADR, lock, review, and mutation reference.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

### CS-SR-034 — Semantic authorization proof

**Root issue:** the static authorization audit trusts authorized-looking names instead of resolving call targets and proving authorization precedes every effect.

**Review evidence:** `AR-007` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** build a resolved interprocedural call graph from operator entry points to effects and cover spoofed names, aliases, indirect calls, branch bypass, and effect-before-authorization.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

### CS-SR-035 — Network query authority

**Root issue:** exact query scope is partly prose and the CEQAnet listing planner accepts caller-supplied base search URLs.

**Review evidence:** `AR-008` in `docs/audits/adversarial_review_2026-08-13.md`.

**Required correction:** encode exact query or request identity in executable policy, remove arbitrary base-URL injection, and reject any request outside reviewed host, path, query-key, query-value, and canonical-identity scope.

**State:** no accepted correction or regression evidence; blocks a new review candidate.

## Failed-review disposition and next handoff

The August 13 reviewer inspected the frozen implementation tree rather than treating this dossier, the PR description, or passing tests as proof. The review failed. No independent-review artifact may record a passing result for the target below, and the prior handoff must not be reused.

### Invalidated review target

```text
4cc3ce763354ea91ef8c4bed28c3ce0b531379c3
```

The historical handoff required a clean checkout and independent digest computation:

```bash
python - <<'PY'
from pathlib import Path
from constructionsight.authority_certification import _reviewed_tree_digest
print(_reviewed_tree_digest(Path('.')))
PY
```

Digest computation intentionally fails closed when any staged, unstaged, or untracked non-permitted review-covered path is dirty. This remains useful doctrine, but the digest of the invalidated target cannot support certification.

### Required adversarial scope for the next candidate

At minimum, independently challenge:

- architecture classification, import boundaries, cycle/capability ownership, and every exception;
- dependency identity, lock/hash provenance, unexpected installed code, Action pins, SBOM provenance, and vulnerability posture;
- network-client inventory, lawful-access constraints, redirect behavior, byte ceilings, retry classification, terminal access-control outcomes, and no-bypass doctrine;
- authorization scope, negative authority, stale state, reuse/expiry, claim consumption, and Boolean-bypass paths;
- persistence atomicity, audit failure, rollback, replay, and concurrency behavior;
- CEQAnet intent-to-implementation consistency;
- ArcGIS bounded acquisition and rehearsal authority boundaries;
- source-registry planning/apply separation;
- adversarial-test coverage, mutation resistance, mirrored-test risk, and absent negative cases;
- resolved-ledger finalization integrity;
- exact-head CI behavior;
- review-tree and worktree binding;
- external-review authenticity; and
- every active defect's original root cause and stated required resolution.

### Required GitHub review

If any problem is found, the reviewer must **not** approve. Findings must first be corrected and regression-tested, and any review-covered correction creates a new candidate requiring a fresh review.

After `CS-SR-028` through `CS-SR-035` are corrected with focused negative regressions and the complete Python 3.11/3.12 matrix passes on a new exact candidate, a fresh reviewer must submit an actual GitHub **APPROVED** pull-request review anchored to that new exact commit:

```text
<new-corrected-review-candidate-sha>
```

The reviewer must be a human GitHub `User` whose login differs from `TruSudo` as both PR author and repository owner.

The resulting artifact must satisfy the exact schema enforced by `authority_certification.py`, including:

```json
{
  "schema_version": "constructionsight.independent-review/v1",
  "status": "passed",
  "reviewer": "github:<reviewer-login>#<review-id>",
  "review_method": "<specific adversarial review methodology>",
  "reviewed_commit": "<new-corrected-review-candidate-sha>",
  "reviewed_tree_digest": "<independently computed lowercase SHA-256 digest>",
  "findings": []
}
```

Canonical CI will independently re-fetch that GitHub review ID and verify its external identity/state/commit binding before the aggregate finalization gate can pass.

At the August 13 failed-review checkpoint, GitHub's PR Reviews API contained **no review objects** for PR #117. No ordinary PR comment, including prior handoff comments, constitutes the required approval. A review of the invalidated target cannot satisfy the future gate.

## Finalization sequence after a corrected candidate and legitimate review

1. create `governance/reviews/independent_review.json` bound to the actual external GitHub approval and independently computed reviewed-tree digest;
2. update this exempt dossier with the reviewer identity, review ID, methodology, digest, and finding disposition;
3. construct strict resolved-ledger entries for every reviewed defect whose correction/regression/review evidence supports closure;
4. remove those same IDs from the active ledger, with active/resolved disjointness mechanically enforced;
5. leave the active ledger with **zero entries** before final certification;
6. run canonical exact-head CI on the resulting finalization head under Python 3.11 and Python 3.12;
7. require the external GitHub review revalidation stage to pass on both jobs;
8. require repository certification to produce **zero findings** on both jobs;
9. require the aggregate quality gate to pass on both jobs;
10. retain and record the final certification artifacts and SHA-256 digests;
11. verify the intended merge/squash result is content-equivalent to the reviewed tree outside the four explicitly permitted finalization paths;
12. only then mark PR #117 ready, reconcile overlapping PR #116, and proceed with merge.

## Historical checkpoint — run #1028

An earlier implementation candidate, `27ae656605591a41aa1ac0ed53c18eecc8a04116`, was validated in run #1028 with 1,096 passing tests on each runtime and 24 active defects plus `REVIEW-001`. That checkpoint was important because it exposed later finalization risks rather than representing final readiness.

Subsequent adversarial work identified and corrected:

- CS-SR-025 — dirty review-worktree binding;
- CS-SR-026 — resolved-ledger/finalization integrity; and
- CS-SR-027 — external independent-review identity authenticity.

Accordingly, #1028 remains historical evidence only. Run #1050 and candidate `4cc3ce763354ea91ef8c4bed28c3ce0b531379c3` are also historical evidence after the August 13 failed review. No current review candidate exists until `CS-SR-028` through `CS-SR-035` are corrected and the complete exact-head matrix passes again.

## Product continuation after hardening

Silent-risk hardening is a prerequisite to, not the completion of, the full ConstructionSight product.

After PR #117 is legitimately reviewed, certified, reconciled, and merged, the next product phases remain:

- collect and independently verify the additional CEQAnet recurring-live-source observations required before another maturity review;
- implement append-only authorization-consumption evidence and separately authorized San Bernardino and Riverside ArcGIS complete rehearsals;
- promote source maturity only from independently verified evidence;
- implement production observation/ingestion orchestration without weakening lawful-access or provenance boundaries;
- advance project-state intelligence and scoring from actual public-record signals;
- implement outreach preview, approval, deduplication, compliance, and delivery evidence before any sending capability;
- implement the map/operator GUI, jobsite views, developer and general-contractor directories, relationship graph, evidence inspector, jurisdiction filters, and lead queue; and
- package the supported operator application only after ingestion, evidence, identity, and authority controls justify that exposure.

Those phases remain intentionally separate from defect closure so product pressure cannot weaken the certification boundary.
