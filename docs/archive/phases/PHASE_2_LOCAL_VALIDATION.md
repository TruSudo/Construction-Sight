# Phase 2 Local Validation

## Status

Phase 2 source registry persistence was locally validated after fixing source-registry upsert flush behavior.

## Initial Failure

The first local test run exposed two persistence defects:

1. `test_source_registry_store_round_trip` returned zero persisted sources inside the same transaction.
2. `test_source_registry_upsert_updates_existing_record` triggered a SQLite unique-constraint failure on repeated upsert.

## Root Cause

The SQLAlchemy session factory was configured with `autoflush=False`. Pending inserts were not flushed before same-transaction reads, so `list_sources()` could not see newly inserted records. Repeated upserts also could not see pending inserts and attempted to insert duplicate rows.

## Fix

`SourceRegistryStore` now explicitly flushes after upsert operations and before source reads.

Fixed file:

```text
src/constructionsight/storage/source_registry.py
```

Fix commit:

```text
3039ccfb94e637a6434a1176d0656c1307d9cee4
```

## Validated Commands

```bash
git pull origin main
source .venv/bin/activate
python -m pytest
constructionsight init-db
constructionsight load-sources data/source_registry.seed.json
constructionsight list-sources
```

## Result

The user reported the corrected test run came back safe.

The earlier CLI database validation also showed all four seed sources loading and listing correctly:

- Riverside County PLUS Online
- San Bernardino County EZOP
- CSLB Public License Search
- CEQAnet State Clearinghouse

## Phase 2 Completion Determination

Phase 2 is considered locally validated.

Next phase: Phase 3 — source verification engine.
