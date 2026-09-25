# CS-SR-056 Permanent Closure Evidence

Defect: `CS-SR-056 — database-schema-evolution`

## Historical root cause

Database initialization depended on SQLAlchemy `create_all` without a repository-owned
schema version or compatibility/migration contract. Existing databases could retain
obsolete or partial shapes while current ORM models assumed a newer schema.

## Resolution

Resolution implementation commit:

`1866453b6cfcf63b6c0cd2af4cbb234daa59581f`

Resolution Git tree:

`93e1e6893e33253adcf921e1739af8972638b4b6`

The corrected implementation adds:

- repository-owned schema version 1;
- a canonical full-schema contract and SHA-256 schema identity;
- fail-closed verification for versioned databases;
- exact-shape adoption for compatible unversioned databases with retained provenance;
- no-mutation rejection for incompatible legacy schemas;
- detection of partial schema-version ledgers, wrong versions, and persisted shape drift;
  and
- an explicit governance substrate for future schema upgrades/migrations.

## Regression evidence

Canonical coverage in `tests/test_schema_governance.py` includes:

- `test_fresh_database_records_governed_schema_version`
- `test_exact_unversioned_schema_is_adopted_with_provenance`
- `test_incompatible_unversioned_schema_fails_without_mutation`
- `test_partial_schema_version_ledger_fails_closed`
- `test_wrong_schema_version_fails_closed`
- `test_versioned_database_rejects_persisted_shape_drift`

Implementation evidence includes:

- `src/constructionsight/storage/database.py`
- `src/constructionsight/storage/schema_governance.py`
- `docs/architecture/database_schema_governance.md`

## Validation

The original remediation head was validated by CI run `36112681123`: both isolated
vulnerability audits passed and both Python quality matrices passed all substantive
checks, failing only the aggregate active-defect enforcement step.

The remediation has since been merged only into the non-main
`assurance/permanent-resolution-integration` branch. Final ledger transition is
conditioned on successful substantive validation of that combined exact head.

This closure preserves the historical finding while permanently retiring the schema
evolution root cause. It does not claim resolution of CS-SR-053 monetary precision.
