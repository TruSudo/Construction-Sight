"""Native reviewed retained CSV source import uses the original real evidence fixture.

No network requests are made. Test original atomic persistence, approval digest
binding, operator-database readback and all denied-by-default controls.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.command_center_ceqanet_retained_import import (
    apply_reviewed_retained_ceqanet_import,
    preview_retained_ceqanet_import,
)
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import create_database_engine, initialize_database
from tests.test_command_center_investigation_bridge import snapshot

_REAL = (
    Path(__file__).resolve().parents[1]
    / "evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json"
)


def _configured(tmp_path: Path) -> tuple[Path, Path, Path]:
    directory = tmp_path / "private"
    directory.mkdir(mode=0o700)
    database = directory / "operator.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    engine.dispose()
    database.chmod(0o600)
    evidence = directory / "one-retained-ceqanet-csv.json"
    evidence.write_bytes(_REAL.read_bytes())
    evidence.chmod(0o600)
    return database, evidence, directory


def test_original_retained_csv_native_import_exact_real_source(
    tmp_path: Path,
) -> None:
    db, evidence, folder = _configured(tmp_path)
    server = make_server(
        snapshot(), 0, folder,
        operator_database=db, operator_ceqanet_csv_evidence=evidence,
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        headers = {"Origin": host}
        with httpx.Client(base_url=host, trust_env=False) as client:
            response = client.get("/api/source-ceqanet-retained-import")
            assert response.status_code == 200, response.text
            preview = response.json()
            assert preview["configured"] is True
            assert preview["available"] is True
            assert preview["planned_write_count"] == 4
            assert len(preview["source_record_keys"]) == 2
            assert preview["network_executed"] is False
            assert preview["persistence_mutated"] is False
            assert preview["source_claims_verified"] is False
            assert preview["commercial_authority_granted"] is False
            assert preview["source_sha256"] == (
                "5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163"
            )
            assert client.get(
                "/api/source-ceqanet-retained-import?write=true"
            ).status_code == 409
            approved = {
                "retained_artifact_sha256": preview["retained_artifact_sha256"],
                "source_sha256": preview["source_sha256"],
                "expected_write_plan_digest": preview["expected_write_plan_digest"],
                "expected_destination_identity": preview["expected_destination_identity"],
                "review_reason": "Approved exact retained public source evidence only.",
                "caller_confirmation": True,
            }
            for invalid in (
                {**approved, "caller_confirmation": False},
                {**approved, "review_reason": "short"},
                {**approved, "retained_artifact_sha256": "f" * 64},
                {**approved, "source_sha256": "f" * 64},
                {**approved, "expected_write_plan_digest": "f" * 64},
                {**approved, "expected_destination_identity": "f" * 64},
                {**approved, "extra": "unreviewed"},
            ):
                response = client.post(
                    "/api/source-ceqanet-retained-apply", json=invalid,
                    headers=headers,
                )
                assert response.status_code == 400, response.text
            assert client.post(
                "/api/source-ceqanet-retained-apply", json=approved,
            ).status_code == 403
            assert client.post(
                "/api/source-ceqanet-retained-apply", json=approved,
                headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            assert client.post(
                "/api/source-ceqanet-retained-apply?ignore=true",
                json=approved, headers=headers,
            ).status_code == 400
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            assert client.get("/api/source-ceqanet-retained-import").status_code == 200
            assert hashlib.sha256(db.read_bytes()).hexdigest() == before
            applied = client.post(
                "/api/source-ceqanet-retained-apply", json=approved, headers=headers,
            )
            assert applied.status_code == 200, applied.text
            result = applied.json()
            assert result["applied_operations"] == 4
            assert result["operator_readback_verified"] is True
            assert result["operator_dashboard_visibility_verified"] is True
            assert result["commercial_authority_granted"] is False
            assert result["source_claims_verified"] is False
            assert result["network_executed"] is False
            assert set(result["source_record_keys"]) == set(preview["source_record_keys"])
            assert evidence.read_bytes() == _REAL.read_bytes()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_retained_csv_native_preview_rejects_changed_and_bound_evidence(
    tmp_path: Path,
) -> None:
    database, evidence, _folder = _configured(tmp_path)
    approved_preview = preview_retained_ceqanet_import(
        database, evidence, None, None,
    )
    assert approved_preview["available"] is True
    bad_payload = {
        "retained_artifact_sha256": approved_preview["retained_artifact_sha256"],
        "source_sha256": approved_preview["source_sha256"],
        "expected_write_plan_digest": approved_preview["expected_write_plan_digest"],
        "expected_destination_identity": approved_preview["expected_destination_identity"],
        "review_reason": "This was approved against the unmodified original source.",
        "caller_confirmation": True,
    }
    raw = json.loads(evidence.read_text("utf-8"))
    evidence.write_text(json.dumps({**raw, "error": "changed"}), encoding="utf-8")
    with pytest.raises(ValueError):
        apply_reviewed_retained_ceqanet_import(
            database, evidence, None, None, bad_payload,
        )
    evidence.write_text(json.dumps({
        "schema_version": "ceqanet_bound_project_capture.v1",
        "live_execution": raw,
        "discovery_binding": {
            "sch_number": "2026030377",
            "source_claimed_county": "Riverside",
        },
    }), encoding="utf-8")
    with pytest.raises(ValueError, match="requires both original listing proofs"):
        preview_retained_ceqanet_import(database, evidence, None, None)
    assert preview_retained_ceqanet_import(
        database, None, None, None,
    )["available"] is False
