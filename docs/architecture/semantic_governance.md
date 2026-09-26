# Semantic governance

ConstructionSight distinguishes six control classes that must not be conflated:

1. **Formatting and typing** detect style, syntax, and type-shape defects.
2. **Repository hygiene** proves that the tracked tree contains no prohibited generated state, secrets, suppressions, skipped tests, or malformed structured files.
3. **Semantic correctness** tests business rules, exact identity, stale-state rejection, replay, negative authority, and failure distinctions.
4. **Architecture integrity** constrains which module families may depend on one another and which capabilities they may acquire.
5. **Authorization and resilience** bind high-impact effects and network execution to exact scope, current state, bounded policy, audit identity, and fail-closed behavior.
6. **Supply-chain trust** binds direct declarations, supported-environment artifact hashes, installed versions, vulnerability results, Action identities, and the SBOM.

Passing one class does not imply passing another.

## Machine-readable contracts

The canonical contracts are:

- `governance/architecture_contract.toml`
- `governance/capability_contract.toml`
- `governance/dependency_contract.toml`
- `governance/network_contract.toml`
- `governance/authorization_contract.toml`
- `governance/adversarial_test_contract.toml`
- `governance/mutation_contract.toml`
- `governance/assurance_contract.toml`

Unknown schema versions, malformed fields, unclassified modules, multiply classified modules, missing artifacts, and code/contract disagreement block certification.

## Architecture doctrine

Every tracked production Python module belongs to exactly one layer. The AST certifier resolves internal imports, constructs the dependency graph, rejects prohibited edges and cycles, and detects undeclared network, persistence, subprocess, and mutation capability acquisition.

Architecture exceptions are not comments. A valid exception identifies one exact source and target module, reason, risk, compensating control, owner, issuance and expiry dates, regression test, and ADR. Wildcards, missing evidence, and expired exceptions are rejected.

## Capability doctrine

Every production module has exactly one stable capability owner. Implemented and guarded capabilities require tests, doctrine, ADR linkage, provenance, compatibility, failure, limitation, negative-constraint, network-policy, and authorization-policy declarations as applicable. Planned or externally blocked capabilities must have no runtime exposure and must state their entry conditions.

The capability registry does not claim that source adapters are operational merely because code exists. Source maturity, lawful access, live validation, and operational coverage remain separate evidence.

## Supply-chain doctrine

Direct, development, and build dependencies are exact declarations governed by the dependency registry. Each supported Python environment has a platform-specific lock whose logical rows bind exact versions to reviewed SHA-256 wheel identities. CI rejects resolver-selected versions, source-distribution fallback, unreviewed alternate artifacts, and unhashed lock entries. Installed-version verification, `pip check`, vulnerability scanning, immutable Action pins, and deterministic SBOM generation are independent required gates. Vulnerability scanning executes in an isolated job; exact installed-distribution identity is enforced immediately before and after executable quality gates.

Every governance file reference is resolved through one canonical repository-containment primitive. Absolute, noncanonical, missing, wrong-kind, symlinked, and repository-escaping evidence, test, ADR, lock, review, or mutation references fail certification. Git mode `120000` entries are prohibited before dependency or audit inputs are consumed.

The current locks certify GitHub-hosted Ubuntu x86_64 environments only. Support for another operating system, architecture, Python implementation, or wheel-tag set requires a separate reviewed lock and CI job.

## Authorization doctrine

A high-impact operation is never authorized by a bare Boolean. Caller confirmation may be an additional gate, but the operative decision binds actor/operator, action, resource, exact scope, current state, granted and denied authority, issuance and validity, reuse, revocation, reason, expected identity, stale-state rule, audit identity, audit event, and failure posture.

Authorization validation is not effect consumption. The protected operation must be atomically reserved in the ConstructionSight-owned SQLite consumption store immediately before its statically owned implementation runs. The durable record binds authority, scope, state, trusted time, allowance, content, implementation, replay policy, and terminal outcome. Exact replay returns the retained committed result; it never repeats the effect. A missing store, concurrent reservation, changed content, terminal failure, or crash-retained in-progress state blocks automatic execution. Caller-selected ledgers, used-ID sets, clocks, stores, and effect implementations are prohibited from production authorized-service signatures.

The current product is a local CLI. An explicit operator identifier is sufficient for current audit identity, but it is not authentication. Hosted authentication, delegation, impersonation, temporary access, elevation, and tenant isolation are mandatory entry conditions for any production hosted GUI.

## Defect invalidation

Every discovered certification defect enters `governance/active_defects.toml`. Active defects are executable blockers. A defect moves to `governance/resolved_defects.toml` only after the correction, regression evidence, required cumulative assurance mode, and exact-tree certification are complete. Findings are never suppressed to preserve a zero-defect statement.

## High-risk review

Changes involving authorization, dependency identity, Actions, network execution, mutation, evidence identity, maturity or promotion, recurrence, workflow state, result correction, sending, architecture, compatibility, cryptographic identity, or certification are high risk. They require Native Maximum Assurance bound to the exact reviewed commit: at least three context-isolated complete deep-scan passes, one separate exact-diff pass, one separate adversarial invariant pass, blind candidate union, complete coverage, zero unresolved or deferred candidates, and zero surviving security mutants. The passes must seek bypasses, authority expansion, stale state, replay, concurrency, fail-open behavior, supply-chain defects, doctrine gaps, and tests that merely mirror implementation.

Native context isolation is a fresh analytical take, not external independence. Review by a different model provider is recorded as `independent_external_model` and is not human approval. An unrelated exact-commit GitHub approval is recorded as `independent_human`. Both are additive; neither reduces the native baseline.

## Unsupported boundaries

ConstructionSight does not currently claim production recurring scheduling, concurrent live acquisition throughput, outreach sending, hosted multiuser identity, tenant isolation, delegation, impersonation, or temporary elevation. Cross-process duplicate prevention for already-governed protected operations is implemented; it does not itself grant scheduling or broader concurrency authority.
