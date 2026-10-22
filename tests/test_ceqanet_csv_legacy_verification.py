"""Archival CEQAnet CSV v1 verification is offline and cannot grant authority."""

from __future__ import annotations

import base64
import hashlib
import json
import socket
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_cli import app
from constructionsight.ceqanet_csv_legacy_verification import (
    verify_archived_ceqanet_csv_execution,
)

_RUNNER = CliRunner()
_URL = "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377"
_BODY = (
    b"\xef\xbb\xbfSCH Number,Title,Lead/Public Agency\r\n"
    b'2026030377,"Warehouse, Phase 2",City of Fontana\r\n'
)


def _digest(payload: dict[str, Any]) -> str:
    """Independently reproduce the archived canonical JSON digest contract."""
    material = {
        k: v for k, v in payload.items()
        if k not in {"executed_at", "execution_digest"}
    }
    return hashlib.sha256(
        json.dumps(
            material, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, default=str,
        ).encode("utf-8")
    ).hexdigest()


def _artifact(body: bytes = _BODY) -> dict[str, Any]:
    """Archived model output includes defaults but no current execution claims."""
    request = {
        "schema_version": "ceqanet_csv_export_request.v1",
        "scope": "project",
        "sch_number": "2026030377",
        "document_id": None,
        "method": "GET",
        "documents_downloaded": False,
        "persistence_authorized": False,
    }
    evidence: dict[str, Any] = {
        "schema_version": "ceqanet_csv_export_execution.v1",
        "request": request,
        "request_url": _URL,
        "final_url": _URL,
        "status_code": 200,
        "content_type": "text/csv",
        "content_disposition": None,
        "body_base64": base64.b64encode(body).decode("ascii"),
        "body_byte_length": len(body),
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "network_executed": True,
        "documents_downloaded": False,
        "persistence_mutated": False,
        "error": None,
        "executed_at": "2026-07-12T12:00:00Z",
    }
    evidence["execution_digest"] = _digest(evidence)
    return evidence


def test_retained_legacy_success_and_new_parser_are_distinct_non_authorizing_states() -> None:
    artifact = _artifact()
    report = verify_archived_ceqanet_csv_execution(artifact)

    assert report["passed"] is True
    assert report["finding_count"] == 0
    assert report["historical_parsed_row_count"] == 1
    assert report["historical_parsed_headers"] == [
        "SCH Number", "Title", "Lead/Public Agency",
    ]
    assert report["current_parser_compatible"] is True
    assert report["current_parser_findings"] == []
    assert report["archive_body_sha256"] == hashlib.sha256(_BODY).hexdigest()
    assert report["historical_claimed_network_executed"] is True
    assert report["network_executed_by_verification"] is False
    assert report["current_source_authorized"] is False
    assert report["persistence_mutated"] is False
    assert report["identity_independently_verified"] is False
    assert report["commercial_authority_granted"] is False


def test_old_header_only_csv_is_historical_not_current_source_evidence() -> None:
    report = verify_archived_ceqanet_csv_execution(_artifact(b"SCH Number,Title\n"))

    assert report["passed"] is True
    assert report["historical_parsed_row_count"] == 0
    assert report["current_parser_compatible"] is False
    assert any("at least one data row" in s for s in report["current_parser_findings"])
    assert report["current_source_authorized"] is False


@pytest.mark.parametrize(
    ("field", "value", "finding"),
    [
        ("request_url", "https://example.invalid/Search?OutputFormat=CSV&Sch=2026030377",
         "request URL"),
        (
            "final_url",
            "https://ceqanet.lci.ca.gov.evil.invalid/Search?OutputFormat=CSV&Sch=2026030377",
            "final URL",
        ),
        ("network_executed", False, "does not claim"),
        ("status_code", 403, "not successful"),
        ("error", "Timeout", "execution error"),
        ("body_byte_length", 999, "byte length mismatch"),
        ("body_sha256", "a" * 64, "SHA-256 mismatch"),
        ("body_base64", "!!invalid!!", "body_base64 is invalid"),
    ],
)
def test_forged_old_artifact_is_rejected_even_with_recalculated_digest(
    field: str, value: object, finding: str,
) -> None:
    corrupted = _artifact()
    corrupted[field] = value
    corrupted["execution_digest"] = _digest(corrupted)
    report = verify_archived_ceqanet_csv_execution(corrupted)

    assert report["passed"] is False
    assert any(finding in s for s in report["findings"])
    assert report["current_parser_compatible"] is False
    assert report["current_source_authorized"] is False


def test_body_tampering_without_recomputed_digest_is_not_accepted() -> None:
    corrupted = _artifact()
    corrupted["body_base64"] = base64.b64encode(b"changed").decode("ascii")

    report = verify_archived_ceqanet_csv_execution(corrupted)

    assert report["passed"] is False
    assert "historical execution canonical digest mismatch" in report["findings"]
    assert "historical body SHA-256 mismatch" in report["findings"]


def test_mismatched_or_extended_old_envelopes_fail_schema_before_interpretation() -> None:
    original = _artifact()
    examples = [
        {**original, "unauthorized": "new field"},
        {**original, "schema_version": "ceqanet_csv_live_execution.v1"},
        {**original, "request": {**original["request"], "scope": "document"}},
        {**original, "request": {**original["request"], "unexpected": True}},
    ]
    for example in examples:
        with pytest.raises(ValueError):
            verify_archived_ceqanet_csv_execution(example)


def test_readonly_cli_accepts_valid_legacy_artifact_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_connection(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("archived verification must never connect to a network")

    monkeypatch.setattr(socket, "create_connection", no_connection)
    path = tmp_path / "historical.json"
    output = tmp_path / "verification.json"
    path.write_text(json.dumps(_artifact()), encoding="utf-8")
    before = path.read_bytes()

    result = _RUNNER.invoke(
        app, ["verify-legacy-execution", str(path), "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["passed"] is True
    assert report["network_executed_by_verification"] is False
    assert report["persistence_mutated"] is False
    assert path.read_bytes() == before


def test_readonly_cli_fails_closed_for_tampering_and_existing_output(tmp_path: Path) -> None:
    path = tmp_path / "historical.json"
    report_path = tmp_path / "report.json"
    artifact = _artifact()
    artifact["body_sha256"] = "0" * 64
    path.write_text(json.dumps(artifact), encoding="utf-8")

    refused = _RUNNER.invoke(
        app, ["verify-legacy-execution", str(path), "--output", str(report_path)],
    )
    assert refused.exit_code != 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passed"] is False
    original = report_path.read_bytes()

    refused_again = _RUNNER.invoke(
        app, ["verify-legacy-execution", str(path), "--output", str(report_path)],
    )
    assert refused_again.exit_code != 0
    assert report_path.read_bytes() == original


def test_readonly_cli_rejects_symlink_source_and_non_object_json(tmp_path: Path) -> None:
    target = tmp_path / "source.json"
    target.write_text(json.dumps(_artifact()), encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    out = tmp_path / "result.json"

    assert _RUNNER.invoke(
        app, ["verify-legacy-execution", str(link), "--output", str(out)],
    ).exit_code != 0
    assert not out.exists()
    target.write_text("[]", encoding="utf-8")
    assert _RUNNER.invoke(
        app, ["verify-legacy-execution", str(target), "--output", str(out)],
    ).exit_code != 0
    assert not out.exists()
