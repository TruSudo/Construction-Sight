# CS-SR-011 Permanent Closure Evidence

Defect: `CS-SR-011 — exact-head-ci`

## Closure criterion

CS-SR-011 is retired only after canonical pull-request CI executes on the exact
last-active ConstructionSight commit and retains the supported Python quality and
vulnerability artifacts needed to distinguish individual sub-gate outcomes from the
aggregate workflow result.

The closure transaction uses the exact last-active commit recorded in
`governance/resolved_defects.toml` as its `resolution_commit`. Raw retained outputs
are authoritative over a GitHub step whose own command completed successfully.

## Exact retained result

GitHub Actions CI run **#1551** (run ID `36193106181`) executed against exact commit
`381a64ecc4e35601453091ac880af0d6328d85a9` and **concluded failure**.

Both Python 3.11 and Python 3.12 quality jobs reached the final
`Enforce all quality gates` step and failed there. The retained repository
certification output is identical on both interpreters and reports exactly two
findings:

- `ASSURANCE-001`: the Native Maximum Assurance report was not yet present.
- `DEFECT-ACTIVE-001`: `CS-SR-011` itself was still active.

The repository/semantic certification command therefore did **not** certify the
repository. Its GitHub step is shown as successful only because the command executed
and retained its output before the final enforcement step evaluated the recorded
failure.

The retained evidence also establishes that the preceding sub-gates completed
successfully, including:

- Ruff and strict mypy.
- Source/test compilation.
- **2,134 / 2,134 tests passed** on both supported Python versions.
- **164 / 164 focused mutants killed**.
- Adapter and source-coverage audits.
- Native assurance preflight.
- GitHub Actions provenance verification.
- Diff hygiene.
- Both isolated vulnerability-audit jobs.

No closure statement may convert those passing sub-gates into a claim that the
aggregate CI run or repository certification passed.

## Retained evidence

The machine-readable run record is retained at
`docs/assurance/evidence/CS-SR-011-ci-1551.json`. It records the exact workflow run,
head SHA, job conclusions, artifact IDs, and SHA-256 digests of the retained
certification outputs used for this correction.

Regression coverage is retained by:

- `tests/test_assurance_preflight_certification.py`
- `tests/test_ci_exact_head_contract.py`
- `tests/test_cs_sr_011_closure_evidence.py`

The final zero-active-defect commit is a subsequent governance-only closure
transaction. Native Maximum Assurance remains a separate finalization requirement
after the active ledger reaches zero.
