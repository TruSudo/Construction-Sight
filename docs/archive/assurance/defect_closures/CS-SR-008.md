# CS-SR-008 Permanent Closure Evidence

## Resolution

The affected supported-environment packages are pinned to reviewed fixed releases in both artifact-hashed locks and fresh isolated vulnerability audits report no active advisory for the exact environment.

Validated resolution head: `f773c926168c6284c171bfe05aac7f729c870ddc`

Resolution Git tree: `d9e084b83ee887ae65e16918592cc9410e06d87a`

Canonical CI run `36117450690` validated that exact head on Python 3.11 and Python 3.12.
Both isolated vulnerability audits passed. Ruff, mypy, compileall, full pytest, focused
mutation certification, adapter/source audits, assurance preflight,
repository/semantic certification, diff hygiene, and environment identity checks passed.
The only failing quality step was the intentional aggregate blocker for remaining active
defects.

## Evidence

- `requirements/py311.lock`
- `requirements/py312.lock`
- `src/constructionsight/vulnerability_certification.py`

## Regression coverage

- `tests/test_vulnerability_certification.py`
- `tests/test_vulnerability_ci_certification.py`

This closure preserves the original finding and retires only its corrected root cause.
Remaining active findings and final assurance obligations are unchanged.
