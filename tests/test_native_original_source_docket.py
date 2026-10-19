"""Native original source candidate docket uses existing atomic staging and readback."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session

import constructionsight.effect_consumption as effects
from constructionsight.ceqa_models import CeqaRecord
from constructionsight.command_center_source_docket import (
    preview_original_source_docket,
)
from constructionsight.live_command_center import make_server
from constructionsight.provenance import Provenance
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore
from constructionsight.storage.effect_consumption_store import EffectConsumptionStore
from tests.test_command_center_investigation_bridge import snapshot


@pytest.fixture
def docket_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    folder = tmp_path / "private"
    folder.mkdir(mode=0o700)
    database = folder / "operator.sqlite3"
    engine = create_database_engine(f"sqlite+pysqlite:///{database}")
    initialize_database(engine)
    with Session(engine) as session, session.begin():
        CeqaStore(session).upsert(CeqaRecord(
            ceqa_key="source:one", title="Original retained construction source",
            county="Riverside", provenance=[
                Provenance(source_name="Original synthetic source",
                           evidence_text="Exact reviewed source evidence")
            ],
        ))
    engine.dispose()
    database.chmod(0o600)
    monkeypatch.setattr(
        effects, "_owned_store",
        lambda: EffectConsumptionStore(tmp_path / "docket-allowances.sqlite3"),
    )
    return folder, database


def test_original_docket_native_http_preview_to_exact_staging_receipt(
    docket_source: tuple[Path, Path],
) -> None:
    folder, database = docket_source
    server = make_server(snapshot(), 0, folder, operator_database=database)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        url = "/api/source-review-docket?kind=ceqa&record_id=source%3Aone"
        with httpx.Client(base_url=host, trust_env=False) as client:
            for malformed in (
                "/api/source-review-docket",
                url + "&unreviewed=1",
                "/api/source-review-docket?kind=permit&record_id=missing",
            ):
                assert client.get(malformed).status_code == 409
            before = hashlib.sha256(database.read_bytes()).hexdigest()
            preflight = client.get(url)
            assert preflight.status_code == 200, preflight.text
            plan = preflight.json()
            assert plan["may_request_staging"] is True
            assert plan["original_staged_history"] == []
            assert plan["original_source_preview"]["preview_id"].startswith(
                "source-candidate-preview:"
            )
            assert plan["commercial_lead_created"] is False
            assert plan["outreach_authorized"] is False
            assert plan["network_executed"] is False
            assert hashlib.sha256(database.read_bytes()).hexdigest() == before
            original = plan["original_source_preview"]
            reviewed = {
                "kind": "ceqa", "record_id": "source:one",
                "expected_preview_id": original["preview_id"],
                "expected_source_sha256": original["normalized_source_sha256"],
                "review_reason": "Preserve exact unapproved source evidence for review.",
                "caller_confirmation": True,
            }
            assert client.post(
                "/api/source-review-docket-stage", json=reviewed,
            ).status_code == 403
            assert client.post(
                "/api/source-review-docket-stage", json=reviewed,
                headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            for invalid in (
                {**reviewed, "caller_confirmation": False},
                {**reviewed, "expected_source_sha256": "0" * 64},
                {**reviewed, "expected_preview_id": "invalid"},
                {**reviewed, "review_reason": "too short"},
                {**reviewed, "unexpected": True},
            ):
                response = client.post(
                    "/api/source-review-docket-stage", json=invalid,
                    headers={"Origin": host},
                )
                assert response.status_code == 400, response.text
            assert client.get(url).json()["original_staged_history"] == []
            receipt = client.post(
                "/api/source-review-docket-stage", json=reviewed,
                headers={"Origin": host},
            )
            assert receipt.status_code == 200, receipt.text
            body = receipt.json()
            assert body["staged_recorded_new"] is True
            assert body["original_stage_entry"]["preview_id"] == original["preview_id"]
            assert body["original_stage_entry"]["commercial_lead_created"] is False
            assert body["original_stage_entry"]["outreach_authorized"] is False
            assert body["original_stage_entry"]["bid_authorized"] is False
            assert body["original_authorization"]["action"] == (
                "stage-source-candidate-review"
            )
            after = client.get(url).json()
            assert after["docket_schema_ready"] is True
            assert len(after["original_staged_history"]) == 1
            assert after["original_staged_history"][0]["stage_id"] == (
                body["original_stage_entry"]["stage_id"]
            )
            assert after["original_source_preview"] == original
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_original_docket_uses_source_identity_and_rejects_substitution(
    docket_source: tuple[Path, Path],
) -> None:
    _, database = docket_source
    report = preview_original_source_docket(
        database, kind="ceqa", record_id="source:one",
    )
    assert report["docket_schema_ready"] is True
    assert report["source_record_mutated"] is False
    for kind, record in (
        ("smarts", "source:one"),
        ("permit", "source:one"),
        ("ceqa", "source:one\ninjected"),
        ("ceqa", "../source:one"),
    ):
        with pytest.raises((ValueError, LookupError)):
            preview_original_source_docket(
                database, kind=kind, record_id=record,
            )
