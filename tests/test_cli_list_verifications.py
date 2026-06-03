import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.cli import app
from constructionsight.models import PlatformFamily, PublicSource, SourceVerificationResult
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore


def test_list_verifications_cli_shows_persisted_records(tmp_path) -> None:
    database_path = tmp_path / "constructionsight.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    seed_record = json.loads(Path("data/source_registry.seed.json").read_text(encoding="utf-8"))[0]
    source = PublicSource.model_validate(seed_record)

    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        SourceRegistryStore(session).upsert_source(source)
        VerificationStore(session).add_result(
            SourceVerificationResult(
                source_name=source.source_name,
                public_url=source.public_url,
                url_reachable=True,
                portal_type_detected=PlatformFamily.CEQANET,
                public_search_available=True,
                login_required=False,
                confidence_score=91,
                notes="Synthetic listed verification.",
            )
        )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "list-verifications",
            "--database-url",
            database_url,
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "Persisted Source Verification Records" in result.output
    assert "Verification Evidence Details" in result.output
    assert "source=CEQAnet State Clearinghouse" in result.output
    assert "platform=ceqanet" in result.output
    assert "reachable=True" in result.output
    assert "public_search=True" in result.output
    assert "login_required=False" in result.output
    assert "confidence=91" in result.output
    assert "notes=Synthetic listed verification." in result.output
    assert "Found 1 verification records." in result.output


def test_list_verifications_cli_handles_empty_database(tmp_path) -> None:
    database_path = tmp_path / "empty.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "list-verifications",
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert "Persisted Source Verification Records" in result.output
    assert "Verification Evidence Details" not in result.output
    assert "Found 0 verification records." in result.output
