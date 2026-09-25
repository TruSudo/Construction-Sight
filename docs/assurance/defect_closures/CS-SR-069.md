# CS-SR-069 Permanent Closure Evidence

## Resolution

The resolver-selected vulnerability scanner bootstrap was replaced by repository-owned deterministic vulnerability certification with fail-closed advisory/source provenance and exact supported-runtime enforcement.

Validated resolution head: `f773c926168c6284c171bfe05aac7f729c870ddc`

Resolution Git tree: `d9e084b83ee887ae65e16918592cc9410e06d87a`

Canonical CI run `36117450690` validated that exact head on Python 3.11 and Python 3.12.
The assurance preflight, repository/semantic certification, quality matrix and both
isolated vulnerability audits passed; the only failing quality step was the intentional
aggregate blocker for remaining active defects.

## Evidence

- `.github/workflows/ci.yml`
- `src/constructionsight/vulnerability_certification.py`
- `src/constructionsight/vulnerability_ci_certification.py`

## Regression coverage

- `tests/test_vulnerability_certification.py`
- `tests/test_vulnerability_ci_certification.py`

This closure preserves the original historical finding and retires only the corrected
assurance/supply-chain root cause.
