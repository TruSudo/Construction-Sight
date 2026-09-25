# CS-SR-011 Permanent Closure Evidence

Defect: `CS-SR-011 — exact-head-ci`

## Closure criterion

CS-SR-011 is retired only after the complete last-active ConstructionSight tree receives canonical pull-request CI on that exact Git commit, with both supported Python quality jobs, both isolated vulnerability audits, retained certification artifacts, focused mutation certification, Native assurance preflight, GitHub Actions provenance verification, repository/semantic certification, and diff hygiene evaluated against the same head.

The closure transaction must use the exact last-active commit recorded in `governance/resolved_defects.toml` as its `resolution_commit` and must not claim success from an earlier branch head.

## Retained evidence

The authoritative evidence is the GitHub Actions CI run and retained certification/vulnerability artifacts associated with the exact `resolution_commit`. Raw retained outputs are authoritative over continue-on-error step presentation.

Regression coverage is retained by:

- `tests/test_ci_exact_head_contract.py`
- `tests/test_assurance_preflight_certification.py`

The final zero-active-defect commit is a subsequent governance-only closure transaction. Native Maximum Assurance remains a separate finalization requirement after the active ledger reaches zero.
