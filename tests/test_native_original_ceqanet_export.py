"""Phase 8 native CEQAnet package/archive parity with original verified services."""

from __future__ import annotations

import hashlib
import json
import threading
import zipfile
from io import BytesIO
from pathlib import Path
from shutil import copyfile

import httpx

from constructionsight.command_center_legacy_export import (
    original_ceqanet_archive_verification,
    original_ceqanet_export,
)
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
            assert client.get(
                "/api/source-ceqanet-report-download", params={"sha256": original_hash}
            ).status_code == 409
            assert client.get(
                "/api/source-ceqanet-report-download", params={"sha256": "0" * 64}
            ).status_code == 409
            assert client.get(
                "/api/source-ceqanet-report-download",
                params={"sha256": original_hash, "extra": "1"},
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
            # Native audit is the original archive CLI verifier, not another
            # ZIP parser. It must retain per-artifact evidence, exact chain
            # binding and all no-write/no-network boundaries.
            verify_url = "/api/source-ceqanet-export-verification"
            for params in (
                {"sha256": "0" * 64},
                {"sha256": original_hash, "other": "x"},
            ):
                assert client.get(verify_url, params=params).status_code == 409
            assert client.get(verify_url).status_code == 409
            checked = client.get(verify_url, params={"sha256": original_hash})
            assert checked.status_code == 200, checked.text
            audit = checked.json()
            assert audit["schema_version"] == (
                "constructionsight.original-ceqanet-archive-verification/v1"
            )
            assert audit["retained_report_sha256"] == original_hash
            assert audit["source_report_binding_verified"] is True
            assert audit["passed"] is True
            assert audit["network_executed"] is False
            assert audit["archive_mutated"] is False
            assert audit["source_database_mutated"] is False
            assert audit["commercial_authority_granted"] is False
            metadata = audit["original_verification"]["metadata"]
            assert metadata["schema_version"] == "ceqanet_operator_archive_verification.v1"
            assert metadata["passed"] is True
            assert metadata["manifest_status"] == "verified"
            assert "archive_path" not in metadata
            assert metadata["verified_count"] == metadata["artifact_count"] >= 5
            assert all(
                entry["status"] == "verified"
                for entry in audit["original_verification"]["artifacts"]
            )
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
                expected_markdown = archive.read("operator-report.md")
                artifacts = {
                    name: archive.read(name)
                    for name in (
                        "operator-package.json", "persistence-preview.json",
                        "write-plan.json", "operator-report.json", "manifest.json",
                    )
                }
            for name, expected_bytes in artifacts.items():
                individual = client.get(
                    "/api/source-ceqanet-artifact-download",
                    params={"sha256": original_hash, "artifact": name},
                )
                assert individual.status_code == 200, individual.text[:500]
                assert individual.content == expected_bytes
                assert individual.headers["content-type"] == "application/json"
                assert individual.headers["cache-control"] == "no-store"
                assert individual.headers["x-content-type-options"] == "nosniff"
                assert individual.headers["content-disposition"] == (
                    f"attachment; filename={name}"
                )
            for invalid in ("../operator-package.json", "not-present.json", ""):
                assert client.get(
                    "/api/source-ceqanet-artifact-download",
                    params={"sha256": original_hash, "artifact": invalid},
                ).status_code == 409
            assert client.get(
                "/api/source-ceqanet-artifact-download",
                params={"sha256": original_hash, "artifact": "operator-package.json",
                        "extra": "1"},
            ).status_code == 409
            assert client.get(
                "/api/source-ceqanet-artifact-download",
                params={"sha256": "0" * 64, "artifact": "operator-package.json"},
            ).status_code == 409
            markdown = client.get(
                "/api/source-ceqanet-report-download", params={"sha256": original_hash}
            )
            assert markdown.status_code == 200, markdown.text[:500]
            assert markdown.headers["content-type"] == "text/markdown; charset=utf-8"
            assert markdown.content == expected_markdown
            again = client.post(
                "/api/source-ceqanet-export", json=request, headers={"Origin": base}
            )
            assert again.status_code == 200, again.text
            assert again.json()["existing_verified_archive"] is True
            # A changed selected chain report must not authorize inspection
            # of an archive that was built against the previous contents.
            report.write_text(json.dumps({
                **_chain_report(), "extra": "substituted",
            }), encoding="utf-8")
            assert client.get(verify_url, params={
                "sha256": original_hash,
            }).status_code == 409
            assert client.post(
                "/api/source-ceqanet-export?extra=1", json=request,
                headers={"Origin": base},
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
    assert hashlib.sha256(report.read_bytes()).hexdigest() != original_hash


def test_original_ceqanet_export_requires_configured_operator_db_and_report(
    tmp_path: Path,
) -> None:
    import pytest

    with pytest.raises(ValueError, match="require an existing operator database"):
        make_server(
            snapshot(), 0, tmp_path / "native",
            operator_ceqanet_chain_report=tmp_path / "missing.json",
        )


def test_original_archive_integrity_checks_chain_binding_not_just_valid_zip(
    tmp_path: Path,
) -> None:
    """A valid archive for report B cannot masquerade as the archive for A."""
    first = tmp_path / "report-a.json"
    second = tmp_path / "report-b.json"
    a = _chain_report()
    b = _chain_report()
    b["metadata"]["archive_review_identity"] = "synthetic alternate source"
    first.write_text(json.dumps(a), encoding="utf-8")
    second.write_text(json.dumps(b), encoding="utf-8")
    digest_a = hashlib.sha256(first.read_bytes()).hexdigest()
    digest_b = hashlib.sha256(second.read_bytes()).hexdigest()
    assert digest_a != digest_b
    native = tmp_path / "native"
    for report, digest in ((first, digest_a), (second, digest_b)):
        result = original_ceqanet_export(
            native, report, expected_report_sha256=digest, caller_confirmation=True,
        )
        assert result["verification_passed"] is True
    export_root = native / "original-ceqanet-exports"
    # Structural integrity remains valid when substituting a separately
    # verified ZIP; only binding to the selected report detects this swap.
    copyfile(export_root / (digest_b + ".zip"), export_root / (digest_a + ".zip"))
    bad = original_ceqanet_archive_verification(
        native, first, expected_report_sha256=digest_a,
    )
    assert bad["original_verification"]["metadata"]["passed"] is True
    assert bad["source_report_binding_verified"] is False
    assert bad["passed"] is False
    assert bad["network_executed"] is False
    assert bad["archive_mutated"] is False
    assert bad["commercial_authority_granted"] is False
