# ConstructionSight Consolidation Defect Triage

Baseline under review: `c00e012075a7c5b1a2c41ce52c277c824adf3161`

Canonical consolidation PR: #153

Exact-head CI run: 36103396415

## Purpose

This document classifies the active defect ledger for consolidation readiness without weakening or bypassing the repository's assurance policy.

The baseline remains frozen. This triage is performed on a separate branch so the exact candidate SHA and its retained CI evidence remain stable while findings are reviewed.

## Current exact-head evidence

On both Python 3.11 and Python 3.12, the exact frozen head completed the following substantive gates successfully:

- exact checkout verification
- tracked symbolic-link rejection
- exact dependency installation and lock verification
- dependency integrity
- deterministic SBOM generation
- pre- and post-gate environment identity verification
- Ruff
- mypy
- source/test compilation
- full pytest
- focused mutation certification
- adapter contract audit
- source adapter coverage audit
- native assurance preflight
- optional independent-review verification path
- GitHub Actions provenance verification path
- authenticated owner-acceptance verification path
- repository and semantic certification audit
- diff hygiene
- isolated vulnerability audit on Python 3.11
- isolated vulnerability audit on Python 3.12

The only failing step is the aggregate `Enforce all quality gates` step, which remains blocked by the active defect / final assurance state.

## Ledger state

- Active defects: 75
- Resolved defects recorded: 0
- Active P0: 45
- Active P1: 26
- Active P2: 4

Therefore a red aggregate gate does not, by itself, show that all 75 root causes remain present in the current implementation.

## Findings with direct current-head remediation evidence

The following findings have present-tense symptoms that are directly contradicted by retained exact-head CI or current workflow structure. They are **closure candidates**, not automatically closed defects. Each still requires defect-specific verification and ledger movement under the assurance contract.

| Defect | Historical manifestation | Current exact-head evidence | Triage status |
|---|---|---|---|
| CS-SR-008 | Known vulnerable locked packages | Both isolated vulnerability audits pass | Closure candidate |
| CS-SR-036 | Locked pip advisory caused mandatory vulnerability failure | Both isolated vulnerability audits pass | Closure candidate |
| CS-SR-065 | Ruff errors in assurance provenance/mutation hardening | Ruff passes on 3.11 and 3.12 | Closure candidate |
| CS-SR-067 | Full pytest failure from non-idempotent workflow test helper | Full pytest passes on 3.11 and 3.12 | Closure candidate |
| CS-SR-068 | Actions pinned to Node-20-era runtime without reviewed Node 24 binding | CI uses immutable v7 action SHAs with reviewed `runtime=node24` annotations; assurance preflight passes | Closure candidate requiring provenance-specific verification |
| CS-SR-069 | Resolver-selected vulnerability scanner bootstrap | Current CI invokes repository-native `constructionsight.vulnerability_certification` against retained source evidence | Closure candidate requiring reproducibility-specific verification |
| CS-SR-070 | Ruff E501 in CI action certification | Ruff passes on 3.11 and 3.12 | Closure candidate |
| CS-SR-071 | Vulnerability Bash steps lacked BASH_ENV neutralization | Current vulnerability steps set `BASH_ENV=/dev/null`; structural assurance preflight passes | Closure candidate |
| CS-SR-072 | Canonical CI exposed to inherited Bash startup/options/functions | Current run steps use explicit `/bin/bash --noprofile --norc -p -e -o pipefail`; assurance preflight passes | Closure candidate requiring adversarial execution regression confirmation |
| CS-SR-073 | Candidate project installation/build code executed before gates | Current quality bootstrap installs the exact locked third-party environment and runs source through `PYTHONPATH`; no editable project install appears in the canonical workflow | Closure candidate |
| CS-SR-074 | AnyIO advisories caused fresh vulnerability failure | Both fresh isolated vulnerability audits pass | Closure candidate requiring exact lock/advisory provenance confirmation |
| CS-SR-075 | Ruff violations and prohibited conditional pytest skip caused structural failure | Ruff, pytest, and native assurance preflight all pass on both supported runtimes | Closure candidate |

## Findings not safe to close from aggregate CI alone

The remaining active findings cover authorization atomicity, network authority, durable evidence semantics, concurrency, trusted time, schema evolution, deep immutability, financial precision, epistemic provenance, public-egress controls, assurance identity/binding, and other semantic invariants.

A passing aggregate test suite is supportive evidence but is not sufficient proof that each such root cause has been eliminated. These findings require defect-specific review against:

1. the exact current implementation,
2. the required resolution text in `governance/active_defects.toml`,
3. dedicated regressions and mutation witnesses where required,
4. current contract/doctrine enforcement,
5. retained evidence tied to the exact candidate tree.

## Recommended closure protocol

For each active finding:

1. Reproduce the historical root cause against the current tree where feasible.
2. Identify the implementation that purports to remediate it.
3. Identify the exact tests, adversarial regressions, and mutation witnesses that protect the remediation.
4. Verify those checks run in canonical CI.
5. Confirm no contract or architecture weakening was used to make the test pass.
6. Record closure evidence tied to the exact commit/tree.
7. Move the defect from `active_defects.toml` to `resolved_defects.toml` only after the repository's required closure predicates are satisfied.
8. Rerun exact-head CI after each coherent closure batch.

## Merge posture

PR #153 should remain draft and unmerged while defect closure is being reconciled.

The correct objective is not to make CI green by deleting, ignoring, or suppressing defect records. The objective is to prove which defects are actually remediated, formally close them with exact-tree evidence, and leave genuinely unresolved defects active.

No change in this triage authorizes a merge to `main`.
