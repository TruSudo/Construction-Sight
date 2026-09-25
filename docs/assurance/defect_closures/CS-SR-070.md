# CS-SR-070 Permanent Closure Evidence

Defect: `CS-SR-070 — assurance-quality-gate-compliance`

## Historical root cause

Action-provenance hardening introduced two Ruff E501 overlong expressions in
`src/constructionsight/ci_action_certification.py`, making the candidate fail the
mandatory lint gate.

## Resolution

The expressions are now compliant without lint suppression, rule weakening, or removal
of the action identity/runtime checks.

Exact validated resolution head: `74598ce80a57c02c87e2d5cde68d3bd172d4bca0`

Resolution Git tree: `200e913fec0c29ef6e3160533737e9ea0b895638`

CI run `36116853382` validated this exact head on Python 3.11 and Python 3.12.
Ruff, mypy, compileall, full pytest, focused mutation certification, adapter/source audits,
assurance preflight, repository/semantic certification, diff hygiene, environment identity,
and both isolated vulnerability audits all passed. The only failing step was the aggregate
gate that intentionally rejects remaining active defects.


## Regression and implementation evidence

- `src/constructionsight/ci_action_certification.py`
- `tests/test_ci_action_certification.py`
- `tests/test_assurance_preflight_certification.py`

Exact-head Ruff and the complete quality matrix pass on both supported runtimes, while
action provenance certification remains enforced.
