"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.storage.orm import Base

DEFAULT_DATABASE_PATH = Path("data/constructionsight.sqlite3")
_ORM_MODULE_NAMES = (
    "constructionsight.storage.domain_orm",
    "constructionsight.storage.intelligence_orm",
    "constructionsight.storage.lead_workflow_orm",
    "constructionsight.storage.movement_identity_orm",
    "constructionsight.storage.parcel_site_orm",
    "constructionsight.storage.result_authority_orm",
)


def database_url_from_path(path: Path = DEFAULT_DATABASE_PATH) -> str:
    """Convert a filesystem path into a SQLite database URL."""

    return f"sqlite:///{path}"


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy database engine."""

    url = database_url or database_url_from_path()
    return create_engine(url, future=True)


def initialize_database(engine: Engine) -> None:
    """Create all known tables.

    SQLAlchemy only creates tables whose ORM classes have been imported into
    metadata. Load every registered ORM module before calling ``create_all()``.
    """

    for module_name in _ORM_MODULE_NAMES:
        import_module(module_name)
    Base.metadata.create_all(engine)


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
