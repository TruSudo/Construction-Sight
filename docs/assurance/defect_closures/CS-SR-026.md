# CS-SR-026 Permanent Closure Evidence

Defect: `CS-SR-026 — defect-closure-ledger-integrity`

## Historical root cause

The prior closure model made cumulative exact-tree assurance a prerequisite for moving
an individual defect to the resolved ledger while the same assurance process required
zero active defects. It also required reviewed defects to close as one all-or-nothing
transaction. That made incremental formal closure circular and unenforceable.

## Resolution

Resolution implementation commit:

`53845f5bfa0d9b9c312de49eadfd7aae0178e8d9`

Resolution Git tree:

`1f2a7265d0c2eb448d994c585a367580f8dd09d1`

The corrected model:

- versions the resolved ledger as `constructionsight.resolved-defects/v2`;
- preserves every historical active fact from an explicit last-active commit;
- binds every resolution to an existing Git commit and exact Git tree;
- requires the correction commit to be present while the finding is still active;
- requires safe retained evidence and regression-test paths;
- requires defect-specific closure evidence;
- prohibits active/resolved overlap and duplicate resolution IDs;
- permits one proven defect to close while unrelated findings remain active; and
- reserves Native Maximum Assurance for final whole-tree zero-active certification.

## Regression evidence

Canonical regression coverage includes:

- `tests/test_review_binding_certification.py`
  - proves one defect can close while another remains active;
  - proves historical defect facts cannot be rewritten;
  - proves nonexistent or non-ancestral resolution commits fail closed.
- `tests/test_governance_contract_schema.py`
  - proves exact resolved-ledger v2 shape;
  - rejects malformed commits/tree IDs;
  - rejects unsafe evidence/regression paths;
  - rejects duplicate IDs and active/resolved overlap;
  - requires safe defect-specific closure evidence.

## Exact-head validation

CI-only PR #168 validates exact implementation head
`53845f5bfa0d9b9c312de49eadfd7aae0178e8d9`.

At the time this closure evidence was prepared, Python 3.12 had completed the full
substantive quality stack successfully and Python 3.11 had likewise passed Ruff, mypy,
compileall, full pytest, mutation certification, adapter/source audits and assurance
preflight. Both isolated vulnerability audits passed. The only expected red condition is
the aggregate gate that intentionally continues to reject remaining active defects.

Final ledger movement does not claim final product certification. It records permanent
resolution of this specific historical root cause while all remaining active findings
continue to block zero-defect certification.
