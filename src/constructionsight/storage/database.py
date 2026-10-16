"""Database engine and session helpers."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from sqlite3 import Connection as SQLiteConnection
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.storage.runtime_artifacts import anchored_artifact_parent
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
    dbapi_connection: Any,
    _connection_record: Any,
) -> None:
    """Enable and verify SQLite referential-integrity enforcement per connection."""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        row = cursor.execute("PRAGMA foreign_keys").fetchone()
    finally:
        cursor.close()
    if row is None or int(row[0]) != 1:
        raise RuntimeError("SQLite foreign-key enforcement could not be enabled")


def create_database_engine(database_url: str | URL | None = None) -> Engine:
    """Create a SQLAlchemy database engine."""

    url = database_url or database_url_from_path()
    engine = create_engine(url, future=True)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def prepare_private_database(path: Path, *, create: bool = True) -> Path:
    """Prepare an owner-only regular SQLite file through the existing anchored file boundary."""
    path = path.absolute()
    with anchored_artifact_parent(path, create_parents=create) as (parent, name):
        directory = os.fstat(parent)
        if directory.st_uid != os.geteuid() or stat.S_IMODE(directory.st_mode) & 0o077:
            raise ValueError("investigation database requires an owner-only directory (0700)")
        if create:
            try:
                descriptor = os.open(
                    name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
                )
            except FileExistsError:
                pass
            else:
                os.close(descriptor)
        info = os.stat(name, dir_fd=parent, follow_symlinks=False)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise ValueError("investigation database must be a private owned regular file (0600)")
    return path


def create_private_database_engine(path: Path, *, create: bool = True) -> Engine:
    """Open the exact private database, rejecting later pathname or permission substitutions."""
    path = prepare_private_database(path, create=create)
    before = path.lstat()
    expected = (before.st_dev, before.st_ino)
    engine = create_database_engine(URL.create("sqlite+pysqlite", database=str(path)))

    def check_file(_connection: Any, _record: Any, _proxy: Any = None) -> None:
        prepare_private_database(path, create=False)
        actual = path.lstat()
        if (actual.st_dev, actual.st_ino) != expected:
            raise ValueError("database identity changed; reopen the data folder")

    event.listen(engine, "connect", check_file)
    event.listen(engine, "checkout", check_file)
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


def ensure_database_transaction(session: Session) -> None:
    """Ensure SQLite reads/savepoints belong to the caller's actual outer transaction.

    sqlite3 legacy transaction control does not BEGIN for SELECT or SAVEPOINT.
    SQLAlchemy still owns commit/rollback; this establishes the missing driver boundary.
    Other drivers already begin through SQLAlchemy's normal transaction machinery.
    """
    connection = session.connection()
    driver = connection.connection.driver_connection
    if isinstance(driver, SQLiteConnection) and not driver.in_transaction:
        connection.exec_driver_sql("BEGIN")


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
