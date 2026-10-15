# Phase 2 — Source Registry Persistence

## Objective

Create a durable source registry database layer for ConstructionSight.

The source registry is the foundation for lawful public-record acquisition. It prevents the project from treating unverified assumptions as operational sources.

## Added Components

- `src/constructionsight/storage/database.py`
  - SQLAlchemy engine creation
  - SQLite default database URL
  - database initialization
  - managed session scope

- `src/constructionsight/storage/orm.py`
  - `SourceRecord` ORM table
  - unique source-name/public-URL constraint
  - indexed jurisdiction, county, source type, platform family, and verification fields

- `src/constructionsight/storage/source_registry.py`
  - `SourceRegistryStore`
  - source upsert
  - bulk source loading
  - source listing
  - source lookup by name
  - ORM-to-Pydantic conversion

- `src/constructionsight/cli.py`
  - `init-db`
  - `load-sources`
  - `list-sources`

- `tests/test_source_registry_store.py`
  - in-memory SQLite round-trip test
  - upsert update test

## Local Validation Commands

```bash
source .venv/bin/activate
python -m pytest
constructionsight init-db
constructionsight load-sources data/source_registry.seed.json
constructionsight list-sources
```

## Known Limitations

- This phase stores only source registry records.
- It does not yet store permits, CEQA records, agenda items, parcels, contractors, or relationship graph data.
- Seed source records remain `unverified` until Phase 3 verification tooling confirms them.
- SQLite is the default local development database. PostgreSQL support remains a later production hardening step.

## Phase 2 Completion Criteria

Phase 2 is complete only when the local validation commands pass and the persisted source list shows the four seed sources:

- CEQAnet State Clearinghouse
- CSLB Public License Search
- San Bernardino County EZOP
- Riverside County PLUS Online
