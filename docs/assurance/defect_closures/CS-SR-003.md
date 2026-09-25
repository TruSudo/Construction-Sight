# CS-SR-003 Permanent Closure Evidence

## Resolution

The current tree uses governed artifact-hashed locks, exact dependency policy, immutable GitHub Action SHAs, deterministic SBOM generation, and isolated vulnerability enforcement.

Validated resolution head: `74598ce80a57c02c87e2d5cde68d3bd172d4bca0`

Resolution Git tree: `200e913fec0c29ef6e3160533737e9ea0b895638`

Canonical CI run `36116853382` evaluated that exact head on Python 3.11 and Python 3.12.
Both isolated vulnerability audits passed. Ruff, mypy, compileall, full pytest, focused
mutation certification, adapter/source audits, Native Maximum Assurance preflight,
repository/semantic certification, diff hygiene, and environment identity checks passed.
The only failing quality step was the aggregate gate that intentionally rejects the
remaining active defect ledger.

## Evidence

- `.github/workflows/ci.yml`
- `governance/dependency_contract.toml`
- `src/constructionsight/supply_chain.py`

## Regression coverage

- `tests/test_ci_action_certification.py`
- `tests/test_supply_chain.py`
- `tests/test_vulnerability_certification.py`

This closure preserves the historical supply chain finding while retiring the corrected root
cause. It does not weaken the remaining active-defect or final assurance requirements.
