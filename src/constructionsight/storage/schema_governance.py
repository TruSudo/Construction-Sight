"""Repository-owned database schema version and compatibility governance."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Engine,
    Integer,
    MetaData,
    String,
    Table,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.sql.schema import ForeignKeyConstraint, UniqueConstraint

from constructionsight.money import money_text, rate_text, storage_money_text
from constructionsight.storage.orm import Base

CURRENT_SCHEMA_VERSION = 2
SCHEMA_MIGRATION_TABLE = "construction_sight_schema_migrations"

_SCHEMA_METADATA = MetaData()
_SCHEMA_MIGRATIONS = Table(
    SCHEMA_MIGRATION_TABLE,
    _SCHEMA_METADATA,
    Column("version", Integer, primary_key=True, nullable=False),
    Column("from_version", Integer, nullable=True),
    Column("migration_id", String(255), nullable=False, unique=True),
    Column("schema_digest", String(64), nullable=False),
    Column("provenance", String(64), nullable=False),
    Column("applied_at", String(64), nullable=False),
)

_V2_EXACT_COLUMNS = {
    "result_ledgers": ("gross_value_exact",),
    "result_share_records": (
        "gross_value_exact",
        "share_rate_exact",
        "share_value_exact",
    ),
}


class SchemaCompatibilityError(ValueError):
    """Raised when persisted database shape cannot be proven compatible."""


def initialize_governed_schema(engine: Engine) -> None:
    """Create, adopt, migrate, or verify the exact repository-owned schema."""

    expected = expected_schema_contract()
    expected_digest = schema_contract_digest(expected)
    inspector = inspect(engine)
    table_names = _user_table_names(inspector)

    if not table_names:
        Base.metadata.create_all(engine)
        _assert_current_shape(engine, expected)
        with engine.begin() as connection:
            _create_migration_table(connection)
            _record_version(
                connection,
                from_version=None,
                migration_id="schema-v2:fresh-create",
                schema_digest=expected_digest,
                provenance="fresh_create",
            )
        _assert_version_state(engine, expected_digest)
        return

    if SCHEMA_MIGRATION_TABLE not in table_names:
        actual = actual_schema_contract(engine)
        if actual != expected:
            raise SchemaCompatibilityError(
                "unversioned database schema does not exactly match the current "
                "repository schema; refusing implicit upgrade"
            )
        with engine.begin() as connection:
            _create_migration_table(connection)
            _record_version(
                connection,
                from_version=None,
                migration_id="schema-v2:adopt-exact-unversioned",
                schema_digest=expected_digest,
                provenance="exact_unversioned_adoption",
            )
        _assert_version_state(engine, expected_digest)
        return

    _assert_migration_table_shape(engine)
    records = _migration_records(engine)
    latest = records[-1]
    if latest["version"] == 1:
        _migrate_v1_to_v2(engine, latest)
    elif latest["version"] != CURRENT_SCHEMA_VERSION:
        raise SchemaCompatibilityError(
            f"unsupported database schema version: {latest['version']}"
        )
    _assert_version_state(engine, expected_digest)
    _assert_current_shape(engine, expected)


def expected_schema_contract(version: int | None = None) -> dict[str, Any]:
    """Return the canonical schema shape for the current or supported prior version."""

    current = {
        table_name: _table_contract_from_metadata(table)
        for table_name, table in sorted(Base.metadata.tables.items())
    }
    target = CURRENT_SCHEMA_VERSION if version is None else version
    if target == CURRENT_SCHEMA_VERSION:
        return current
    if target != 1:
        raise SchemaCompatibilityError(f"unsupported schema contract version: {target}")
    prior = copy.deepcopy(current)
    for table_name, column_names in _V2_EXACT_COLUMNS.items():
        table = prior.get(table_name)
        if table is None:
            raise SchemaCompatibilityError(
                f"schema v1 reconstruction is missing table: {table_name}"
            )
        table["columns"] = [
            column
            for column in table["columns"]
            if column["name"] not in set(column_names)
        ]
    return prior


def actual_schema_contract(engine: Engine) -> dict[str, Any]:
    """Return canonical persisted schema shape excluding governance metadata."""

    inspector = inspect(engine)
    return {
        table_name: _table_contract_from_inspector(inspector, table_name)
        for table_name in sorted(_user_table_names(inspector))
        if table_name != SCHEMA_MIGRATION_TABLE
    }


def schema_contract_digest(contract: dict[str, Any]) -> str:
    """Return full SHA-256 identity for one canonical schema contract."""

    encoded = json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def current_schema_record(engine: Engine) -> dict[str, Any]:
    """Return the current schema-version record after history validation."""

    _assert_migration_table_shape(engine)
    rows = _migration_records(engine)
    row = rows[-1]
    if row["version"] != CURRENT_SCHEMA_VERSION:
        raise SchemaCompatibilityError(
            f"unsupported database schema version: {row['version']}"
        )
    return row


def _migration_records(engine: Engine) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(_SCHEMA_MIGRATIONS).order_by(_SCHEMA_MIGRATIONS.c.version)
        ).mappings().all()
    if not rows:
        raise SchemaCompatibilityError("schema migration ledger must contain a version record")
    records = [dict(row) for row in rows]
    versions = [record["version"] for record in records]
    if versions not in ([1], [2], [1, 2]):
        raise SchemaCompatibilityError(
            f"schema migration ledger has unsupported version history: {versions}"
        )
    if versions == [1, 2] and records[-1]["from_version"] != 1:
        raise SchemaCompatibilityError("schema v2 migration must declare from_version = 1")
    if versions in ([1], [2]) and records[0]["from_version"] is not None:
        raise SchemaCompatibilityError("initial schema record must not declare from_version")
    return records


def _migrate_v1_to_v2(engine: Engine, record: dict[str, Any]) -> None:
    """Migrate the exact governed v1 result schema to fixed-decimal persistence."""

    expected_v1 = expected_schema_contract(1)
    expected_v1_digest = schema_contract_digest(expected_v1)
    if record["schema_digest"] != expected_v1_digest:
        raise SchemaCompatibilityError(
            "schema v1 digest does not match the repository-supported predecessor"
        )
    if actual_schema_contract(engine) != expected_v1:
        raise SchemaCompatibilityError(
            "schema v1 persisted shape does not match the supported predecessor"
        )

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE result_ledgers ADD COLUMN gross_value_exact VARCHAR(64)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE result_share_records ADD COLUMN gross_value_exact VARCHAR(64)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE result_share_records ADD COLUMN share_rate_exact VARCHAR(64)"
        )
        connection.exec_driver_sql(
            "ALTER TABLE result_share_records ADD COLUMN share_value_exact VARCHAR(64)"
        )
        _backfill_exact_result_values(connection)
        _record_version(
            connection,
            from_version=1,
            migration_id="schema-v2:fixed-decimal-result-accounting",
            schema_digest=schema_contract_digest(expected_schema_contract()),
            provenance="governed_v1_to_v2",
        )


def _backfill_exact_result_values(connection: Connection) -> None:
    ledger_rows = connection.execute(
        text("SELECT id, payload_json FROM result_ledgers")
    ).mappings()
    for row in ledger_rows:
        payload = _payload_object(row["payload_json"], "result ledger")
        gross = payload.get("gross_value")
        exact = None if gross is None else storage_money_text(gross)
        connection.execute(
            text(
                "UPDATE result_ledgers SET gross_value_exact = :exact "
                "WHERE id = :row_id"
            ),
            {"exact": exact, "row_id": row["id"]},
        )

    share_rows = connection.execute(
        text("SELECT id, payload_json FROM result_share_records")
    ).mappings()
    for row in share_rows:
        payload = _payload_object(row["payload_json"], "result share")
        try:
            gross_exact = money_text(payload["gross_value"])
            rate_exact = rate_text(payload["share_rate"])
            share_exact = money_text(payload["share_value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaCompatibilityError(
                "result share payload cannot be migrated to fixed-decimal storage"
            ) from exc
        connection.execute(
            text(
                "UPDATE result_share_records "
                "SET gross_value_exact = :gross, share_rate_exact = :rate, "
                "share_value_exact = :share WHERE id = :row_id"
            ),
            {
                "gross": gross_exact,
                "rate": rate_exact,
                "share": share_exact,
                "row_id": row["id"],
            },
        )


def _payload_object(raw: object, label: str) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise SchemaCompatibilityError(f"{label} payload is not text")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaCompatibilityError(f"{label} payload is malformed JSON") from exc
    if not isinstance(payload, dict):
        raise SchemaCompatibilityError(f"{label} payload must be a JSON object")
    return {str(key): value for key, value in payload.items()}


def _assert_current_shape(engine: Engine, expected: dict[str, Any]) -> None:
    actual = actual_schema_contract(engine)
    if actual != expected:
        raise SchemaCompatibilityError(
            "persisted database schema does not match the repository schema contract"
        )


def _assert_version_state(engine: Engine, expected_digest: str) -> None:
    record = current_schema_record(engine)
    if record["schema_digest"] != expected_digest:
        raise SchemaCompatibilityError(
            "persisted schema digest does not match the repository schema contract"
        )


def _create_migration_table(connection: Connection) -> None:
    _SCHEMA_MIGRATIONS.create(connection, checkfirst=False)


def _record_version(
    connection: Connection,
    *,
    from_version: int | None,
    migration_id: str,
    schema_digest: str,
    provenance: str,
) -> None:
    connection.execute(
        _SCHEMA_MIGRATIONS.insert().values(
            version=CURRENT_SCHEMA_VERSION,
            from_version=from_version,
            migration_id=migration_id,
            schema_digest=schema_digest,
            provenance=provenance,
            applied_at=datetime.now(UTC).isoformat(),
        )
    )


def _assert_migration_table_shape(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = _user_table_names(inspector)
    if SCHEMA_MIGRATION_TABLE not in tables:
        raise SchemaCompatibilityError("schema migration ledger is missing")
    actual = _table_contract_from_inspector(inspector, SCHEMA_MIGRATION_TABLE)
    expected = _table_contract_from_metadata(_SCHEMA_MIGRATIONS)
    if actual != expected:
        raise SchemaCompatibilityError("schema migration ledger shape is invalid")


def _user_table_names(inspector: Any) -> set[str]:
    return {
        name
        for name in inspector.get_table_names()
        if not name.startswith("sqlite_")
    }


def _table_contract_from_metadata(table: Table) -> dict[str, Any]:
    columns = [
        {
            "name": column.name,
            "type": _type_contract(column.type),
            "nullable": bool(column.nullable),
            "primary_key": bool(column.primary_key),
        }
        for column in table.columns
    ]
    unique_constraints = sorted(
        {
            (
                constraint.name or "",
                tuple(column.name for column in constraint.columns),
            )
            for constraint in table.constraints
            if isinstance(constraint, UniqueConstraint)
        }
    )
    foreign_keys = sorted(
        (
            tuple(element.parent.name for element in constraint.elements),
            constraint.referred_table.name,
            tuple(element.column.name for element in constraint.elements),
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    indexes = sorted(
        (
            index.name or "",
            bool(index.unique),
            tuple(column.name for column in index.columns),
        )
        for index in table.indexes
    )
    primary_key = tuple(column.name for column in table.primary_key.columns)
    return {
        "columns": columns,
        "primary_key": primary_key,
        "unique_constraints": unique_constraints,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
    }


def _table_contract_from_inspector(inspector: Any, table_name: str) -> dict[str, Any]:
    columns = [
        {
            "name": column["name"],
            "type": _type_contract(column["type"]),
            "nullable": bool(column["nullable"]),
            "primary_key": bool(column.get("primary_key", False)),
        }
        for column in inspector.get_columns(table_name)
    ]
    pk = inspector.get_pk_constraint(table_name)
    unique_constraints = sorted(
        (
            item.get("name") or "",
            tuple(item.get("column_names") or ()),
        )
        for item in inspector.get_unique_constraints(table_name)
    )
    foreign_keys = sorted(
        (
            tuple(item.get("constrained_columns") or ()),
            item.get("referred_table") or "",
            tuple(item.get("referred_columns") or ()),
        )
        for item in inspector.get_foreign_keys(table_name)
    )
    indexes = sorted(
        (
            item.get("name") or "",
            bool(item.get("unique", False)),
            tuple(item.get("column_names") or ()),
        )
        for item in inspector.get_indexes(table_name)
    )
    return {
        "columns": columns,
        "primary_key": tuple(pk.get("constrained_columns") or ()),
        "unique_constraints": unique_constraints,
        "foreign_keys": foreign_keys,
        "indexes": indexes,
    }


def _type_contract(sql_type: Any) -> dict[str, Any]:
    affinity = getattr(sql_type, "_type_affinity", type(sql_type))
    return {
        "affinity": affinity.__name__.lower(),
        "length": getattr(sql_type, "length", None),
    }
