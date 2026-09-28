# Database Schema Governance

ConstructionSight treats persisted database shape as an authoritative compatibility
boundary. Application startup must not silently reinterpret an older SQLite schema
through current ORM models.

## Current schema version

The repository-owned schema version is `1`.

The exact ORM schema contract is canonicalized across:

- tables and columns;
- SQL type affinity and declared length;
- nullability and primary-key membership;
- primary-key column order;
- unique constraints;
- foreign keys; and
- named indexes.

The contract is bound to a full SHA-256 digest.

## Initialization states

### Fresh database

A database with no user tables is created from the current ORM metadata, verified
against the canonical schema contract, then receives an append-only schema
migration record with provenance `fresh_create`.

### Exact unversioned database

An existing database without the schema migration ledger is not modified until its
entire persisted schema is proven exactly equal to the current repository contract.
Only an exact match may be adopted as version 1, with provenance
`exact_unversioned_adoption`.

### Versioned database

A versioned database must contain the supported version record, the recorded schema
digest must equal the repository contract digest, and the live persisted schema
must still equal that contract. Wrong versions, missing records, malformed
migration-ledger shape, or schema drift fail closed.

### Incompatible legacy database

No implicit migration is attempted. The application refuses initialization before
creating the schema migration ledger. Future schema changes must be implemented as
explicit repository-owned migrations with their own provenance and regressions.

## Security and integrity rationale

`Base.metadata.create_all()` alone is insufficient for an existing database: it
can create missing tables but does not prove that old columns, constraints, indexes,
or incompatible table shapes are absent. ConstructionSight therefore treats
schema compatibility as a verified precondition to application effects.
