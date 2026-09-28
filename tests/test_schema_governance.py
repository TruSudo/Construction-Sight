from __future__ import annotations

from sqlalchemy import inspect

from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
)
from constructionsight.storage.orm import Base
from constructionsight.storage.schema_governance import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_MIGRATION_TABLE,
    SchemaCompatibilityError,
    current_schema_record,
)


def test_fresh_database_records_governed_schema_version() -> None:
    engine = create_database_engine("sqlite:///:memory:")

    initialize_database(engine)

    record = current_schema_record(engine)
    assert record["version"] == CURRENT_SCHEMA_VERSION
    assert record["from_version"] is None
    assert record["provenance"] == "fresh_create"
    assert len(record["schema_digest"]) == 64
    assert SCHEMA_MIGRATION_TABLE in inspect(engine).get_table_names()


def test_exact_unversioned_schema_is_adopted_with_provenance() -> None:
    bootstrap = create_database_engine("sqlite:///:memory:")
    initialize_database(bootstrap)

    legacy = create_database_engine("sqlite:///:memory:")
    Base.metadata.create_all(legacy)
    assert SCHEMA_MIGRATION_TABLE not in inspect(legacy).get_table_names()

    initialize_database(legacy)

    record = current_schema_record(legacy)
    assert record["version"] == CURRENT_SCHEMA_VERSION
    assert record["migration_id"] == "schema-v1:adopt-exact-unversioned"
    assert record["provenance"] == "exact_unversioned_adoption"


def test_incompatible_unversioned_schema_fails_without_mutation() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE incompatible_legacy (id INTEGER PRIMARY KEY, stale TEXT)"
        )

    try:
        initialize_database(engine)
    except SchemaCompatibilityError as exc:
        assert "unversioned database schema" in str(exc)
    else:
        raise AssertionError("incompatible unversioned schema must fail closed")

    assert set(inspect(engine).get_table_names()) == {"incompatible_legacy"}


def test_partial_schema_version_ledger_fails_closed() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"DELETE FROM {SCHEMA_MIGRATION_TABLE}"
        )

    try:
        initialize_database(engine)
    except SchemaCompatibilityError as exc:
        assert "exactly one version-1 record" in str(exc)
    else:
        raise AssertionError("partial schema ledger must fail closed")


def test_wrong_schema_version_fails_closed() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"UPDATE {SCHEMA_MIGRATION_TABLE} SET version = 999"
        )

    try:
        initialize_database(engine)
    except SchemaCompatibilityError as exc:
        assert "unsupported database schema version" in str(exc)
    else:
        raise AssertionError("unsupported schema version must fail closed")


def test_versioned_database_rejects_persisted_shape_drift() -> None:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    table_name = sorted(Base.metadata.tables)[0]
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f'ALTER TABLE "{table_name}" ADD COLUMN unexpected_schema_drift TEXT'
        )

    try:
        initialize_database(engine)
    except SchemaCompatibilityError as exc:
        assert "persisted database schema" in str(exc)
    else:
        raise AssertionError("versioned schema drift must fail closed")
