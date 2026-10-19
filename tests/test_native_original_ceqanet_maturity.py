"""Original CEQAnet source maturity is verified from retained bytes only."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_service import (
    build_ceqanet_csv_encoding_replay,
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_maturity_proposal_service import (
    build_ceqanet_source_maturity_proposal,
)
from constructionsight.command_center_ceqanet_maturity import (
    original_retained_ceqanet_maturity,
)
from constructionsight.live_command_center import make_server
from constructionsight.models import PublicSource, VerificationStatus
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot

_ROOT = Path(__file__).resolve().parents[1]
_SOURCE = _ROOT / "evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json"


def _retained(tmp_path: Path) -> tuple[Path, Path, Path]:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    database = folder / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    registry = [
        PublicSource.model_validate(x)
        for x in json.loads((_ROOT / "data/source_registry.seed.json").read_text())
    ]
    with managed_session(session_factory(engine)) as session:
        SourceRegistryStore(session).upsert_many(registry)
    engine.dispose()
    database.chmod(0o600)
    evidence = folder / "retained.json"
    evidence.write_bytes(_SOURCE.read_bytes())
    evidence.chmod(0o600)
    return database, evidence, folder


def test_original_native_maturity_matches_independent_original_builders(tmp_path: Path) -> None:
    database, evidence, _folder = _retained(tmp_path)
    original_bytes = evidence.read_bytes()
    before = database.read_bytes()
    result = original_retained_ceqanet_maturity(database, evidence)
    assert result["available"] is True
    assert result["observed_encoding"] == "windows-1252"
    assert result["observed_row_count"] == 2
    assert result["original_replay_verification"]["passed"] is True
    assert result["original_maturity_verification"]["passed"] is True
    assert result["original_maturity_proposal"]["decision"] == "keep_partial"
    assert result["retained_artifact_sha256"] == hashlib.sha256(original_bytes).hexdigest()
    assert not any(result[key] for key in (
        "network_executed", "persistence_mutated", "registry_promoted",
        "access_policy_authorized", "recurring_collection_authorized",
        "commercial_authority_granted",
    ))
    execution = CeqanetCsvLiveExecution.model_validate(json.loads(original_bytes))
    replay = build_ceqanet_csv_encoding_replay(execution, max_retained_rows=1_000)
    verify = verify_ceqanet_csv_encoding_replay(execution, replay)
    sources = [
        PublicSource.model_validate(x)
        for x in json.loads((_ROOT / "data/source_registry.seed.json").read_text())
    ]
    # Original SQLite registry order is county then jurisdiction, not seed-file order.
    sources.sort(key=lambda source: (source.jurisdiction.county, source.jurisdiction.name))
    expected = build_ceqanet_source_maturity_proposal(sources, execution, replay, verify)
    assert result["original_replay_digest"] == replay.replay_digest
    assert result["original_maturity_proposal"]["proposal_digest"] == expected.proposal_digest
    assert result["original_maturity_proposal"]["blockers"] == expected.blockers
    assert result["original_maturity_proposal"]["limitations"] == expected.limitations
    assert evidence.read_bytes() == original_bytes
    assert database.read_bytes() == before
    serialized = json.dumps(result)
    assert "retained_body_base64" not in serialized


def test_native_original_maturity_route_is_read_only_and_exact(tmp_path: Path) -> None:
    database, evidence, folder = _retained(tmp_path)
    server = make_server(
        snapshot(), 0, folder,
        operator_database=database,
        operator_ceqanet_csv_evidence=evidence,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            received = client.get("/api/source-ceqanet-maturity-audit")
            assert received.status_code == 200, received.text
            result = received.json()
            assert result["original_maturity_verification"]["passed"] is True
            assert result["registry_promoted"] is False
            assert result["network_executed"] is False
            assert client.get(
                "/api/source-ceqanet-maturity-audit?execute=true"
            ).status_code == 400
            assert client.post(
                "/api/source-ceqanet-maturity-audit", json={"apply": True},
                headers={"Origin": host},
            ).status_code in (400, 404, 405)
            assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_original_maturity_unconfigured_and_rejected_evidence(tmp_path: Path) -> None:
    database, evidence, _folder = _retained(tmp_path)
    missing = original_retained_ceqanet_maturity(database, None)
    assert missing["available"] is False
    assert missing["network_executed"] is False
    assert original_retained_ceqanet_maturity(None, evidence)["available"] is False
    raw = json.loads(evidence.read_text())
    evidence.write_text(json.dumps({
        "schema_version": "ceqanet_bound_project_capture.v1",
        "live_execution": raw,
        "discovery_binding": {"sch_number": "2026030377"},
    }))
    with pytest.raises(ValueError, match="separate original discovery proof"):
        original_retained_ceqanet_maturity(database, evidence)
    evidence.write_text(json.dumps({**raw, "error": "altered retained source"}))
    with pytest.raises(ValueError, match="digest mismatch"):
        original_retained_ceqanet_maturity(database, evidence)
    evidence.write_bytes(_SOURCE.read_bytes())
    evidence.chmod(0o600)
    # A nonpartial source is not evidence for a keep-partial maturity decision.
    engine = create_database_engine(f"sqlite:///{database}")
    with managed_session(session_factory(engine)) as session:
        store = SourceRegistryStore(session)
        sources = store.list_sources()
        ceqa = next(item for item in sources if item.platform_family.value == "ceqanet")
        store.upsert_source(ceqa.model_copy(update={
            "verification_status": VerificationStatus.UNVERIFIED,
        }))
    engine.dispose()
    with pytest.raises(ValueError, match="registry status partial"):
        original_retained_ceqanet_maturity(database, evidence)
