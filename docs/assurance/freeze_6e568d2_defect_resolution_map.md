# ConstructionSight exact-freeze defect resolution map

Frozen implementation commit: `6e568d2c266550be14f50f1270f4a5d13889d787`

Canonical frozen merge candidate: PR #157

## Scope

This is a non-certifying resolution map for the 75 records in
`governance/active_defects.toml`. It does not change either defect ledger and does
not authorize a merge.

The purpose is to prepare the one-shot reviewed closure transaction required by
ADR-0008 and `defect_closure_certification.py`. Formal closure is intentionally
deferred until every reviewed defect is accounted for, the exact-tree assurance
passes are complete, and authenticated owner acceptance is available.

## Exact-head quality state

GitHub Actions run `36105667808` evaluated the exact frozen implementation.

Both supported runtime matrices completed the substantive quality stack:

- Python 3.11 isolated vulnerability audit: passed
- Python 3.12 isolated vulnerability audit: passed
- exact checkout / symbolic-link rejection: passed
- exact lock and dependency integrity: passed
- deterministic SBOM: passed
- Ruff: passed
- mypy: passed
- compileall: passed
- full pytest: passed
- focused mutation certification: passed
- adapter contract audit: passed
- source adapter coverage audit: passed
- native assurance preflight: passed
- repository and semantic certification audit: passed
- diff hygiene: passed
- post-gate environment identity: passed

The quality jobs remain red only at the aggregate `Enforce all quality gates`
step. The preflight implementation explicitly permits only two transaction
blockers before finalization: `ASSURANCE-001` and `DEFECT-ACTIVE-001`.

## Closure invariant

The current closure certifier requires the finalization transaction to:

1. Bind a frozen reviewed implementation commit and exact reviewed active-defect
   digest.
2. Preserve every reviewed defect's original ID, severity, area, root cause,
   discovery commit, and required-resolution text.
3. Empty the active ledger.
4. Account for every reviewed active ID exactly once in the resolved ledger.
5. Bind every closure to an existing `resolution_commit` that is an ancestor of
   the reviewed implementation commit.
6. Preserve every previously resolved entry unchanged.
7. Keep the reviewed implementation commit ancestral to the finalization head.

Therefore defects must not be removed from the active ledger merely because a
present-day aggregate test passes.

## Historical implementation baseline

The September 21 non-certifying progress snapshot classified the 75 records as:

- 42 correction mechanisms evidenced
- 25 partially corrected
- 8 unresolved
- 0 formally closed

That snapshot predates the current frozen implementation and is used only to
prioritize fresh verification.

### Historically unresolved set requiring first-priority fresh review

- CS-SR-045 — lawful-access-fact-authority
- CS-SR-046 — epistemic-provenance-authority
- CS-SR-047 — derived-identity-integrity
- CS-SR-048 — operational-confidence-gating
- CS-SR-049 — duplicate-review-gate
- CS-SR-052 — result-ledger-content-identity
- CS-SR-053 — financial-decimal-integrity
- CS-SR-056 — database-schema-evolution

These eight findings must be treated as unresolved until current-tree implementation,
negative-case regressions, and ancestry evidence establish otherwise.

### Historically partial set requiring defect-specific confirmation

CS-SR-007, CS-SR-011, CS-SR-018, CS-SR-023, CS-SR-027, CS-SR-034,
CS-SR-043, CS-SR-044, CS-SR-050, CS-SR-051, CS-SR-054, CS-SR-055,
CS-SR-057, CS-SR-058, CS-SR-059, CS-SR-060, CS-SR-061, CS-SR-065,
CS-SR-067, CS-SR-068, CS-SR-070, CS-SR-071, CS-SR-072, CS-SR-073,
and CS-SR-074.

No partial finding is promoted solely from the aggregate green substantive matrix.

## Direct current-head remediation signals

The following historical symptoms now have strong exact-head contrary evidence and
should be verified early for closure ancestry:

- CS-SR-008 / CS-SR-036 / CS-SR-074: exact isolated vulnerability audits now pass
  on both supported runtimes.
- CS-SR-065 / CS-SR-070 / CS-SR-075: Ruff now passes on both supported runtimes.
- CS-SR-067 / CS-SR-075: full pytest now passes on both supported runtimes.
- CS-SR-068: canonical Actions are pinned to immutable reviewed Node-24-runtime
  identities and the native assurance preflight passes.
- CS-SR-069: vulnerability certification is repository-native and source-evidence
  bound rather than a resolver-selected scanner bootstrap.
- CS-SR-071: security-critical vulnerability Bash steps neutralize
  `BASH_ENV`.
- CS-SR-072: canonical run steps use explicit startup-isolated Bash invocation.
- CS-SR-073: the quality bootstrap uses the exact locked third-party environment
  and source via `PYTHONPATH`, without editable candidate installation.

These are resolution candidates, not resolved records.

## Fresh verification sequence

1. Re-review the eight historically unresolved findings against the frozen tree.
2. Re-review the 25 historically partial findings, starting with P0 items.
3. For each finding, identify the exact implementation commit that introduced the
   correction and prove it is ancestral to the frozen commit.
4. Bind the dedicated regression/adversarial tests and mutation witnesses required
   by the original `required_resolution`.
5. Confirm those tests are exercised by canonical CI and that no policy weakening
   or suppression was used.
6. Reconcile all 75 records into a complete proposed resolution table.
7. Only after the table is complete, execute the required native assurance passes
   on the exact frozen tree.
8. After assurance evidence is frozen and owner acceptance is authenticated,
   perform the mechanically constrained active-to-resolved ledger transaction.
9. Rerun canonical exact-head CI on the finalization head.
10. Keep PR #157 draft until the final gate is genuinely green and the owner
    explicitly authorizes merge.

## Current merge posture

`main` remains unchanged.

PR #157 is the only canonical frozen consolidation candidate. Ongoing development
branches must not be substituted for this SHA during assurance or defect closure.
