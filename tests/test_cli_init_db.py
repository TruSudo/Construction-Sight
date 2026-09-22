from sqlalchemy import inspect
from typer.testing import CliRunner

from constructionsight.cli import app
from constructionsight.storage.database import create_database_engine


def test_init_db_creates_default_directory_on_first_run(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["init-db"])
    assert result.exit_code == 0, result.output
    database = tmp_path / "data" / "constructionsight.sqlite3"
    assert database.is_file()
    engine = create_database_engine(f"sqlite:///{database}")
    try:
        assert {"domain_ceqa_records", "domain_permits"}.issubset(
            inspect(engine).get_table_names()
        )
    finally:
        engine.dispose()
