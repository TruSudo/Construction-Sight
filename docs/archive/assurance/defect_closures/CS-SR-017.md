# CS-SR-017 Permanent Closure Evidence

## Resolution

The adversarial contract certifier enforces the mandatory category/matrix schema, safe test references, exclusions, and nonblank branch/mutation/property/concurrency doctrine with negative fixtures.

Validated resolution head: `74598ce80a57c02c87e2d5cde68d3bd172d4bca0`

Resolution Git tree: `200e913fec0c29ef6e3160533737e9ea0b895638`

Canonical CI run `36116853382` evaluated that exact head on Python 3.11 and Python 3.12.
Both isolated vulnerability audits passed. Ruff, mypy, compileall, full pytest, focused
mutation certification, adapter/source audits, Native Maximum Assurance preflight,
repository/semantic certification, diff hygiene, and environment identity checks passed.
The only failing quality step was the aggregate gate that intentionally rejects the
remaining active defect ledger.

## Evidence

- `governance/adversarial_test_contract.toml`
- `src/constructionsight/adversarial_contract_certification.py`

## Regression coverage

- `tests/test_adversarial_contract_certification.py`

This closure preserves the historical adversarial contract doctrine finding while retiring the corrected root
cause. It does not weaken the remaining active-defect or final assurance requirements.
