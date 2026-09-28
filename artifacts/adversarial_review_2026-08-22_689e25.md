# Complete-tree adversarial review continuation — `689e25c`

Review target: `689e25cd9bfc36facceb0e1d271eb13b86b2aebc`

This record continues the frozen review captured in
`artifacts/adversarial_baseline_2026-08-21.md`. The reviewed snapshot was
reconstructed from GitHub and all 613 tracked files were verified against their
Git blob identities before analysis. The review used a repository-wide baseline
pass plus focused network, authorization, persistence, domain, and governance
passes, followed by source-level validation and root-cause reconciliation.

This is an internal adversarial review record. It is not an independent human
review, an approval, a defect-resolution record, or a repository certification.
No defect is moved from the active ledger by this review.

## Newly registered root causes

- `CS-SR-060` — generic source readiness and verification derive executable
  host authority from the untrusted registry URL itself. A canonical URL for a
  loopback, private, link-local, reserved, or other internal destination can
  therefore authorize its own bounded `HEAD` or `GET`. Exact URL binding,
  redirect denial, disabled ambient proxy authority, and response-size ceilings
  limit but do not remove the SSRF and bounded internal-response disclosure.
- `CS-SR-061` — single-use decisions, per-UTC-date CEQAnet evidence allowances,
  and recurring-run attempt identities are consumed through caller-selected,
  invocation-local, absent, or stale state. Without one ConstructionSight-owned
  atomic reservation, one logical authorization or attempt can produce multiple
  network or persistence effects.

The active ledger therefore contains 61 defects. `CS-SR-039` and `CS-SR-040`
retain their implementation and regression counterevidence at this head, but
remain active pending legitimate reviewed-history closure and a distinct real
human GitHub `APPROVED` review on the exact reviewed commit.

## Reconciled manifestations

- CI recognition of required commands through textual prefixes and positions is
  additional `CS-SR-006`/`CS-SR-014` evidence, not a new root.
- Mutation certification can classify collection, syntax, setup, or other
  non-semantic failures as killed mutants. This is the already frozen
  `CS-SR-017` manifestation that a referenced test does not prove a semantic
  adversarial witness.
- A repository author can change substantive independent-review artifact claims
  after obtaining an ordinary exact-commit approval because the GitHub review
  does not authenticate the artifact digest. This remains `CS-SR-027`.
- The shared mutable CI report directory lets contributor-controlled tests alter
  earlier retained reports. Externally protected step outcomes and logs remain
  counterevidence; the unbound retained-evidence claim is a `CS-SR-046`
  manifestation.
- A CEQAnet operator ZIP can contain correctly formed entries not declared by its
  manifest while verification reports `passed=true`. The incomplete provenance
  claim is a `CS-SR-046` manifestation; unbounded decompression remains
  `CS-SR-055`.
- Runtime/network contract drift, higher-layer effect injection, trusted-time
  gaps, path containment and no-follow races, stale state transitions, mutable
  historical rows, partial identities, floating-point money, schema evolution,
  domain invariants, cross-artifact commit ordering, and nested mutability remain
  within `CS-SR-004`, `CS-SR-043` through `CS-SR-059` as applicable.

## Rejected candidate

Source-derived text reaches a Markdown report and color-disabled Rich output,
but the repository contains no Markdown-to-HTML renderer, automatic publisher,
shell interpolation, or demonstrated terminal-control sink. This is retained as
output-context hardening guidance rather than registered as a security defect.

## Required continuation

1. Keep the pull request draft and all 61 defects active.
2. Remediate `CS-SR-060` and `CS-SR-061` through governed implementation,
   regression, mutation, and exact Python 3.11/3.12 evidence transactions.
3. Resume the dependency-ordered remediation sequence without treating code-level
   countermeasures as reviewed closure.
4. After every active defect has implementation and evidence, perform a fresh
   complete-tree adversarial review, obtain a distinct real-human exact-head
   `APPROVED` GitHub review, and only then run defect-closure certification.
