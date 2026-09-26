# CS-SR-067 Permanent Closure Evidence

Defect: `CS-SR-067 — assurance-quality-gate-compliance`

## Historical root cause

A semantic CI-permission test helper attempted to recreate the same temporary workflow
directory without idempotent directory creation. Full pytest failed with FileExistsError
even though the production permission certifier was otherwise functioning.

## Resolution

The current test helper is idempotent and the complete canonical pytest and mutation
matrices execute successfully on both supported Python versions.

Exact validated resolution head: `74598ce80a57c02c87e2d5cde68d3bd172d4bca0`

Resolution Git tree: `200e913fec0c29ef6e3160533737e9ea0b895638`

CI run `36116853382` validated this exact head on Python 3.11 and Python 3.12.
Ruff, mypy, compileall, full pytest, focused mutation certification, adapter/source audits,
assurance preflight, repository/semantic certification, diff hygiene, environment identity,
and both isolated vulnerability audits all passed. The only failing step was the aggregate
gate that intentionally rejects remaining active defects.


## Regression and implementation evidence

- `tests/test_ci_permissions_certification.py`
- `tests/test_assurance_preflight_certification.py`
- `src/constructionsight/ci_permissions_certification.py`

The exact-head repository certification also proceeds successfully; only the separately
tracked active-defect/final-assurance aggregate condition remains.
