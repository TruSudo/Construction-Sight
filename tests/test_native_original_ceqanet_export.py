"""Phase 8 native CEQAnet package/archive parity with original verified services."""

from __future__ import annotations

import hashlib
import json
import threading
import zipfile
from io import BytesIO
from pathlib import Path

import httpx

from constructionsight.live_command_center import make_server
from constructionsight.storage.database import create_database_engine, initialize_database
from tests.test_ceqanet_operator_export import _chain_report
from tests.test_command_center_investigation_bridge import snapshot


def test_native_ceqanet_retained_chain_report_builds_verified_zip_only_on_confirmation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{source}")
    initialize_database(engine)
    engine.dispose()
    report = tmp_path / "original-chain-report.json"
    report.write_text(json.dumps(_chain_report()), encoding="utf-8")
    original_hash = hashlib.sha256(report.read_bytes()).hexdigest()
    native = tmp_path / "private"
    server = make_server(
        snapshot(), 0, native,
        operator_database=source, operator_ceqanet_chain_report=report,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=base, trust_env=False) as client:
            status = client.get("/api/source-ceqanet-export-status")
            assert status.status_code == 200, status.text
            assert status.json()["retained_report_sha256"] == original_hash
            assert status.json()["network_executed"] is False
            request = {
                "expected_report_sha256": original_hash,
                "caller_confirmation": True,
            }
            assert client.get("/api/source-ceqanet-export-status?x=1").status_code == 409
            assert client.post(
                "/api/source-ceqanet-export", json=request
            ).status_code == 403
            assert client.post(
                "/api/source-ceqanet-export", json=request,
                headers={"Origin": "https://untrusted.example"},
            ).status_code == 403
            assert client.post(
                "/api/source-ceqanet-export",
                json={**request, "caller_confirmation": False},
                headers={"Origin": base},
            ).status_code == 400
            assert client.post(
                "/api/source-ceqanet-export",
                json={**request, "expected_report_sha256": "f" * 64},
                headers={"Origin": base},
            ).status_code == 400
            assert client.get(
                "/api/source-ceqanet-export-download", params={"sha256": "0" * 64}
            ).status_code == 409
            created = client.post(
                "/api/source-ceqanet-export", json=request, headers={"Origin": base}
            )
            assert created.status_code == 200, created.text
            payload = created.json()
            assert payload["verification_passed"] is True
            assert payload["existing_verified_archive"] is False
            assert payload["commercial_actions_authorized"] is False
            assert payload["network_executed"] is False
            download = client.get(payload["archive_url"])
            assert download.status_code == 200, download.text[:500] if (
                download.status_code != 200
            ) else ""
            assert download.headers["content-type"] == "application/zip"
            assert hashlib.sha256(download.content).hexdigest() == payload["archive_sha256"]
            with zipfile.ZipFile(BytesIO(download.content)) as archive:
                assert "manifest.json" in archive.namelist()
                assert "operator-report.md" in archive.namelist()
                assert "operator-package.json" in archive.namelist()
            again = client.post(
                "/api/source-ceqanet-export", json=request, headers={"Origin": base}
            )
            assert again.status_code == 200, again.text
            assert again.json()["existing_verified_archive"] is True
            assert client.post(
                "/api/source-ceqanet-export?extra=1", json=request,
                headers={"Origin": base},
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert hashlib.sha256(report.read_bytes()).hexdigest() == original_hash


def test_original_ceqanet_export_requires_configured_operator_db_and_report(
    tmp_path: Path,
) -> None:
    import pytest

    with pytest.raises(ValueError, match="require an existing operator database"):
        make_server(
            snapshot(), 0, tmp_path / "native",
            operator_ceqanet_chain_report=tmp_path / "missing.json",
        )
