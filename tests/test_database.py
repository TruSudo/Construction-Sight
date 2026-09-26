from sqlalchemy import text

from constructionsight.storage.database import create_database_engine


def test_sqlite_foreign_keys_are_enabled_on_every_connection() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
