import json
from pathlib import Path

from typer.testing import CliRunner

import constructionsight.operator_services.ceqanet_discovery_service as discovery_operator
from constructionsight import cli
from constructionsight.ceqanet_discovery_http import CeqanetDiscoveryResult
from constructionsight.models import PublicSource
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore


def _successful_discovery() -> CeqanetDiscoveryResult:
    return CeqanetDiscoveryResult(
        url="https://ceqanet.lci.ca.gov/Search/Advanced",
        reachable=True,
        status_code=200,
        advanced_search_available=True,
        sch_number_field_detected=True,
        document_type_field_detected=True,
        date_field_detected=True,
        lead_agency_field_detected=True,
        notes="Synthetic persisted CLI discovery.",
    )


def test_ceqanet_discovery_converts_to_source_verification_result() -> None:
    discovery = CeqanetDiscoveryResult(
        url="https://ceqanet.lci.ca.gov/Search/Advanced",
        reachable=True,
        status_code=200,
        advanced_search_available=True,
        sch_number_field_detected=True,
        document_type_field_detected=True,
        date_field_detected=True,
        lead_agency_field_detected=True,
        notes="Synthetic conversion test.",
    )

    result = discovery.to_source_verification_result(
        source_name="CEQAnet State Clearinghouse",
        source_url="https://ceqanet.opr.ca.gov/",
    )

    assert result.source_name == "CEQAnet State Clearinghouse"
    assert str(result.public_url) == "https://ceqanet.opr.ca.gov/"
    assert result.url_reachable is True
    assert result.portal_type_detected.value == "ceqanet"
    assert result.public_search_available is True
    assert result.login_required is False
    assert result.confidence_score == 95
    assert result.raw_observations["discovery_url"] == "https://ceqanet.lci.ca.gov/Search/Advanced"
    assert result.raw_observations["status_code"] == 200


def test_discover_ceqanet_cli_persists_verification_result(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        discovery_operator, "discover_ceqanet_public_search", _successful_discovery
    )

    database_path = tmp_path / "constructionsight.sqlite3"
    database_url = f"sqlite+pysqlite:///{database_path}"
    runner = CliRunner()
    source_payload = json.loads(
        Path("data/source_registry.seed.json").read_text(encoding="utf-8")
    )[0]
    source_model = PublicSource.model_validate(source_payload)
    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        SourceRegistryStore(session).upsert_source(source_model)

    result = runner.invoke(
        cli.app,
        [
            "discover-ceqanet",
            "--execute-live",
            "--persist",
            "--database-url",
            database_url,
            "--registry-path",
            "data/source_registry.seed.json",
            "--operator-id",
            "operator:test",
            "--authorization-reason",
            "Review and retain bounded CEQAnet discovery evidence.",
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Public Search Discovery" in result.output
    assert "Persisted CEQAnet discovery verification" in result.output

    engine = create_database_engine(database_url)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        latest = VerificationStore(session).list_latest()
        source = SourceRegistryStore(session).get_by_name("CEQAnet State Clearinghouse")

    assert len(latest) == 1
    assert latest[0].source_name == "CEQAnet State Clearinghouse"
    assert latest[0].url_reachable is True
    assert latest[0].portal_type_detected == "ceqanet"
    assert latest[0].public_search_available is True
    assert latest[0].confidence_score == 95

    raw_observations = json.loads(latest[0].raw_observations_json)
    assert raw_observations["discovery_url"] == "https://ceqanet.lci.ca.gov/Search/Advanced"
    assert raw_observations["confidence_score"] == 95

    assert source is not None
    assert source.verification_status == source_model.verification_status
    assert source.confidence_score == source_model.confidence_score
