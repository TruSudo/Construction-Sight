from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from constructionsight.storage.database import create_database_engine, initialize_database
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
