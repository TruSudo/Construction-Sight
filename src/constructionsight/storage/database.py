"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.storage.schema_governance import initialize_governed_schema

DEFAULT_DATABASE_PATH = Path("data/constructionsight.sqlite3")
_ORM_MODULE_NAMES = (
    "constructionsight.storage.domain_orm",
    "constructionsight.storage.intelligence_orm",
    "constructionsight.storage.lead_workflow_orm",
    "constructionsight.storage.source_candidate_docket_orm",
    "constructionsight.storage.movement_identity_orm",
    "constructionsight.storage.parcel_site_orm",
    "constructionsight.storage.result_authority_orm",
)


def database_url_from_path(path: Path = DEFAULT_DATABASE_PATH) -> str:
    """Convert a filesystem path into a SQLite database URL."""

    return f"sqlite:///{path}"


def _enable_sqlite_foreign_keys(
    dbapi_connection: SQLiteConnection,
    _connection_record: object,
) -> None:
    """Enable and verify SQLite foreign-key enforcement for every connection."""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        row = cursor.execute("PRAGMA foreign_keys").fetchone()
    finally:
        cursor.close()
    if row is None or int(row[0]) != 1:
        raise RuntimeError("SQLite foreign-key enforcement could not be enabled")


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy database engine with governed SQLite integrity."""

    url = database_url or database_url_from_path()
    engine = create_engine(url, future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def initialize_database(engine: Engine) -> None:
    """Create, adopt, or verify the exact governed database schema.

    SQLAlchemy only knows tables whose ORM classes have been imported into
    metadata. Load every registered ORM module before schema governance runs.
    """

    for module_name in _ORM_MODULE_NAMES:
        import_module(module_name)
    initialize_governed_schema(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured SQLAlchemy session factory."""

    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def managed_session(factory: sessionmaker[Session]) -> Iterator[Session]:
    """Provide a transactional session scope."""

    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
