import hashlib
import json
from datetime import datetime
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


def _expected_integrity_hash(payload: dict) -> str:
    scoped_payload = {
        "metadata": payload["metadata"],
        "record_count": payload["record_count"],
        "records": payload["records"],
    }
    canonical = json.dumps(
        scoped_payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _assert_integrity_block(payload: dict) -> None:
    integrity = payload["integrity"]
    assert integrity["algorithm"] == "sha256"
    assert integrity["canonicalization"] == "json.dumps(sort_keys=True,separators=(',',':'),default=str)"
    assert integrity["payload_scope"] == "metadata,record_count,records"
    assert integrity["payload_sha256"] == _expected_integrity_hash(payload)


def test_export_verifications_cli_writes_machine_readable_json(tmp_path) -> None:
    database_path = tmp_path / "constructionsight.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    output_path = tmp_path / "exports" / "verification_records.json"
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
                confidence_score=93,
                notes="Synthetic exported verification.",
                raw_observations={"source": "synthetic", "quality": "high"},
            )
        )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "export-verifications",
            str(output_path),
            "--database-url",
            database_url,
            "--limit",
            "5",
        ],
    )

    assert result.exit_code == 0
    assert "Exported 1 verification records" in result.output
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["record_count"] == 1
    assert len(payload["records"]) == 1
    _assert_integrity_block(payload)

    metadata = payload["metadata"]
    assert metadata["schema_version"] == "verification_export.v1"
    assert metadata["export_type"] == "source_verification_records"
    assert metadata["application"] == "ConstructionSight"
    assert metadata["limit"] == 5
    generated_at = datetime.fromisoformat(metadata["generated_at"])
    assert generated_at.tzinfo is not None

    record = payload["records"][0]
    assert record["source_name"] == "CEQAnet State Clearinghouse"
    assert record["public_url"] == "https://ceqanet.opr.ca.gov/"
    assert record["url_reachable"] is True
    assert record["portal_type_detected"] == "ceqanet"
    assert record["public_search_available"] is True
    assert record["login_required"] is False
    assert record["confidence_score"] == 93
    assert record["notes"] == "Synthetic exported verification."
    assert record["raw_observations"] == {"quality": "high", "source": "synthetic"}


def test_export_verifications_cli_handles_empty_database(tmp_path) -> None:
    database_path = tmp_path / "empty.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    output_path = tmp_path / "empty_export.json"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "export-verifications",
            str(output_path),
            "--database-url",
            database_url,
        ],
    )

    assert result.exit_code == 0
    assert "Exported 0 verification records" in result.output
    assert output_path.exists()

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    _assert_integrity_block(payload)
    assert payload["metadata"]["schema_version"] == "verification_export.v1"
    assert payload["metadata"]["export_type"] == "source_verification_records"
    assert payload["metadata"]["application"] == "ConstructionSight"
    assert payload["metadata"]["limit"] == 20
    assert datetime.fromisoformat(payload["metadata"]["generated_at"]).tzinfo is not None
    assert payload["record_count"] == 0
    assert payload["records"] == []
