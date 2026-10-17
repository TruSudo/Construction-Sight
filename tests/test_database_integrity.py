from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.storage.database import (
    create_database_engine,
    create_private_database_engine,
    initialize_database,
)
from constructionsight.storage.orm import VerificationRecord


def test_sqlite_foreign_keys_are_enabled_on_every_primary_connection() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_declared_source_verification_foreign_key_is_runtime_enforced() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    initialize_database(engine)

    with Session(engine) as session:
        session.add(
            VerificationRecord(
                source_id=999999,
                source_name="missing-source",
                public_url="https://example.test/",
                checked_at=datetime(2026, 9, 26, tzinfo=UTC),
                url_reachable=True,
                portal_type_detected="unknown",
                confidence_score=0,
                raw_observations_json="{}",
            )
        )
        with pytest.raises(IntegrityError):
            session.flush()


def test_private_investigation_database_enforces_foreign_keys_on_reconnect(tmp_path: Path) -> None:
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    engine = create_private_database_engine(private / "investigations.sqlite3")
    initialize_database(engine)
    for _ in range(2):
        with engine.connect() as connection:
            assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
            with pytest.raises(IntegrityError):
                connection.execute(text(
                    "INSERT INTO source_verifications "
                    "(source_id, source_name, public_url, checked_at, url_reachable, "
                    "portal_type_detected, confidence_score, raw_observations_json) "
                    "VALUES (999999, 'missing', 'https://example.test/', "
                    "'2026-10-17', 1, 'unknown', 0, '{}')"
                ))
            connection.rollback()
        engine.dispose()
