"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from constructionsight.storage.orm import Base

DEFAULT_DATABASE_PATH = Path("data/constructionsight.sqlite3")


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
    metadata. Import ORM modules here so `create_all()` sees source-registry,
    normalized domain, intelligence-layer, movement, identity, lead workflow,
    and result ledger tables.
    """

    import constructionsight.storage.domain_orm  # noqa: F401
    import constructionsight.storage.intelligence_orm  # noqa: F401
    import constructionsight.storage.lead_workflow_orm  # noqa: F401
    import constructionsight.storage.movement_identity_orm  # noqa: F401

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
