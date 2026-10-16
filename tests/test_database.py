from sqlalchemy import text

from constructionsight.storage.database import create_database_engine


def test_private_database_rejects_substitution_and_symlinks(tmp_path):
    import os

    import pytest

    from constructionsight.storage.database import create_private_database_engine

    tmp_path.chmod(0o700)
    path = tmp_path / "private.sqlite3"
    engine = create_private_database_engine(path)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
    replacement = tmp_path / "replacement.sqlite3"
    replacement.write_bytes(b"")
    replacement.chmod(0o600)
    os.replace(replacement, path)
    with pytest.raises(ValueError, match="identity changed"):
        engine.connect()
    engine.dispose()
    link = tmp_path / "link.sqlite3"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="regular file"):
        create_private_database_engine(link)
    path.chmod(0o644)
    with pytest.raises(ValueError, match="regular file"):
        create_private_database_engine(path)


# Regression: CS-SR-081
def test_sqlite_foreign_keys_are_enabled_on_every_connection() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
