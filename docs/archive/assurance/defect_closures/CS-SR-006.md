# CS-SR-006 Permanent Closure Evidence

## Resolution

Canonical repository certification now parses and enforces the governance surfaces with stable findings and fail-closed schema/semantic checks inside CI.

Validated resolution head: `74598ce80a57c02c87e2d5cde68d3bd172d4bca0`

Resolution Git tree: `200e913fec0c29ef6e3160533737e9ea0b895638`

Canonical CI run `36116853382` evaluated that exact head on Python 3.11 and Python 3.12.
Both isolated vulnerability audits passed. Ruff, mypy, compileall, full pytest, focused
mutation certification, adapter/source audits, Native Maximum Assurance preflight,
repository/semantic certification, diff hygiene, and environment identity checks passed.
The only failing quality step was the aggregate gate that intentionally rejects the
remaining active defect ledger.

## Evidence

- `src/constructionsight/governance_certification.py`
- `src/constructionsight/governance_contract_schema.py`
- `src/constructionsight/repository_certification.py`

## Regression coverage

- `tests/test_governance_certification.py`
- `tests/test_governance_contract_schema.py`
- `tests/test_repository_certification.py`

This closure preserves the historical repository certification finding while retiring the corrected root
cause. It does not weaken the remaining active-defect or final assurance requirements.
