from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_export_cli import app
from constructionsight.ceqanet_csv_export_models import (
    CeqanetCsvExportExecution,
    CeqanetCsvExportRequest,
    CeqanetCsvScope,
)
from constructionsight.ceqanet_csv_export_service import (
    build_ceqanet_csv_export_url,
    execute_ceqanet_csv_export,
    parse_ceqanet_csv_bytes,
    verify_ceqanet_csv_execution,
)

runner = CliRunner()


@dataclass
class _Response:
    status_code: int
    content: bytes
    url: str
    headers: dict[str, str]


class _Client:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[tuple[str, bool, float]] = []

    def get(
        self,
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
    ) -> _Response:
        self.calls.append((url, follow_redirects, timeout))
        return self.response


def _project_request() -> CeqanetCsvExportRequest:
    return CeqanetCsvExportRequest(
        scope=CeqanetCsvScope.PROJECT,
        sch_number="2026030377",
    )


def _csv_body() -> bytes:
    return (
        "\ufeffSCH Number,Title,Lead/Public Agency\r\n"
        '2026030377,"Warehouse, Phase 2",City of Fontana\r\n'
    ).encode("utf-8")


def test_project_url_matches_observed_official_contract() -> None:
    request = _project_request()

    assert build_ceqanet_csv_export_url(request) == (
        "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377"
    )


def test_document_url_matches_observed_official_contract() -> None:
    request = CeqanetCsvExportRequest(
        scope=CeqanetCsvScope.DOCUMENT,
        sch_number="2026070311",
        document_id=1,
    )

    assert build_ceqanet_csv_export_url(request) == (
        "https://ceqanet.lci.ca.gov/Search?DocumentId=1&OutputFormat=CSV&Sch=2026070311"
    )


def test_request_rejects_scope_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="cannot include document_id"):
        CeqanetCsvExportRequest(
            scope=CeqanetCsvScope.PROJECT,
            sch_number="2026030377",
            document_id=1,
        )

    with pytest.raises(ValueError, match="require document_id"):
        CeqanetCsvExportRequest(
            scope=CeqanetCsvScope.DOCUMENT,
            sch_number="2026070311",
        )


def test_parser_preserves_headers_quotes_and_source_text() -> None:
    report = parse_ceqanet_csv_bytes(
        _csv_body(),
        source_url=build_ceqanet_csv_export_url(_project_request()),
    )

    assert report.headers == ["SCH Number", "Title", "Lead/Public Agency"]
    assert report.row_count == 1
    assert report.records[0].row_number == 2
    assert report.records[0].values == {
        "SCH Number": "2026030377",
        "Title": "Warehouse, Phase 2",
        "Lead/Public Agency": "City of Fontana",
    }
    assert report.body_byte_length == len(_csv_body())
    assert len(report.body_sha256) == 64


def test_parser_rejects_duplicate_or_extra_columns() -> None:
    with pytest.raises(ValueError, match="headers must be unique"):
        parse_ceqanet_csv_bytes(
            b"SCH,SCH\n1,2\n",
            source_url="https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377",
        )

    with pytest.raises(ValueError, match="more values than headers"):
        parse_ceqanet_csv_bytes(
            b"SCH,Title\n1,Title,unexpected\n",
            source_url="https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377",
        )


def test_execution_requires_explicit_live_authorization() -> None:
    with pytest.raises(ValueError, match="explicit live authorization"):
        execute_ceqanet_csv_export(_project_request(), execute_live=False)


def test_successful_execution_is_tamper_evident_and_verifiable() -> None:
    request = _project_request()
    request_url = build_ceqanet_csv_export_url(request)
    client = _Client(
        _Response(
            status_code=200,
            content=_csv_body(),
            url=request_url,
            headers={
                "content-type": "text/csv; charset=utf-8",
                "content-disposition": 'attachment; filename="CEQAnet.csv"',
            },
        )
    )

    execution = execute_ceqanet_csv_export(
        request,
        execute_live=True,
        client=client,
        timeout_seconds=12.5,
    )
    verification = verify_ceqanet_csv_execution(execution)

    assert client.calls == [(request_url, True, 12.5)]
    assert execution.status_code == 200
    assert execution.body_bytes() == _csv_body()
    assert execution.documents_downloaded is False
    assert execution.persistence_mutated is False
    assert verification.passed is True
    assert verification.findings == []
    assert verification.parsed_row_count == 1
    assert verification.parsed_headers == ["SCH Number", "Title", "Lead/Public Agency"]


def test_verifier_rejects_body_tampering_even_with_valid_base64() -> None:
    request = _project_request()
    request_url = build_ceqanet_csv_export_url(request)
    execution = execute_ceqanet_csv_export(
        request,
        execute_live=True,
        client=_Client(
            _Response(
                status_code=200,
                content=_csv_body(),
                url=request_url,
                headers={"content-type": "text/csv"},
            )
        ),
    )
    tampered = execution.model_copy(
        update={"body_base64": base64.b64encode(b"SCH\nchanged\n").decode("ascii")}
    )

    verification = verify_ceqanet_csv_execution(tampered)

    assert verification.passed is False
    assert "CEQAnet CSV execution digest mismatch" in verification.findings
    assert "CSV body byte length does not match retained bytes" in verification.findings
    assert "CSV body SHA-256 does not match retained bytes" in verification.findings


def test_verifier_preserves_http_failure_without_claiming_csv_success() -> None:
    request = _project_request()
    request_url = build_ceqanet_csv_export_url(request)
    execution = execute_ceqanet_csv_export(
        request,
        execute_live=True,
        client=_Client(
            _Response(
                status_code=403,
                content=b"Forbidden",
                url=request_url,
                headers={"content-type": "text/plain"},
            )
        ),
    )

    verification = verify_ceqanet_csv_execution(execution)

    assert verification.passed is False
    assert "CSV response status is not 200: 403" in verification.findings
    assert verification.parsed_row_count is None


def test_verifier_rejects_host_query_and_persistence_drift() -> None:
    request = _project_request()
    execution = CeqanetCsvExportExecution(
        request=request,
        request_url="https://example.invalid/Search?OutputFormat=CSV&Sch=2026030377",
        final_url="https://ceqanet.lci.ca.gov/Search?Sch=2026030377&OutputFormat=CSV",
        status_code=200,
        content_type="text/csv",
        body_base64=base64.b64encode(_csv_body()).decode("ascii"),
        body_byte_length=len(_csv_body()),
        body_sha256="0" * 64,
        network_executed=True,
        persistence_mutated=False,
        execution_digest="0" * 64,
    )

    verification = verify_ceqanet_csv_execution(execution)

    assert verification.passed is False
    assert "CSV request URL is outside the approved official HTTPS host" in verification.findings
    assert "CSV final URL query does not match the request contract" in verification.findings


def test_plan_cli_emits_request_without_network() -> None:
    result = runner.invoke(app, ["plan", "--sch", "2026030377"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["request"]["scope"] == "project"
    assert payload["network_executed"] is False
    assert payload["request_url"].endswith("OutputFormat=CSV&Sch=2026030377")


def test_parse_and_verify_cli_operate_offline(tmp_path: Path) -> None:
    csv_path = tmp_path / "project.csv"
    parse_path = tmp_path / "parse.json"
    execution_path = tmp_path / "execution.json"
    verification_path = tmp_path / "verification.json"
    csv_path.write_bytes(_csv_body())

    parse_result = runner.invoke(
        app,
        [
            "parse",
            str(csv_path),
            "--source-url",
            build_ceqanet_csv_export_url(_project_request()),
            "--output",
            str(parse_path),
        ],
    )
    assert parse_result.exit_code == 0
    assert json.loads(parse_path.read_text(encoding="utf-8"))["row_count"] == 1

    request_url = build_ceqanet_csv_export_url(_project_request())
    client = _Client(
        _Response(
            status_code=200,
            content=_csv_body(),
            url=request_url,
            headers={"content-type": "text/csv"},
        )
    )
    execution = execute_ceqanet_csv_export(
        _project_request(),
        execute_live=True,
        client=client,
    )
    execution_path.write_text(
        json.dumps(execution.model_dump(mode="json")),
        encoding="utf-8",
    )

    verify_result = runner.invoke(
        app,
        [
            "verify",
            str(execution_path),
            "--output",
            str(verification_path),
        ],
    )
    assert verify_result.exit_code == 0
    assert json.loads(verification_path.read_text(encoding="utf-8"))["passed"] is True


def test_execution_model_rejects_unknown_fields() -> None:
    request_url = build_ceqanet_csv_export_url(_project_request())
    payload: dict[str, Any] = {
        "request": _project_request().model_dump(mode="json"),
        "request_url": request_url,
        "final_url": request_url,
        "status_code": 200,
        "body_base64": "",
        "body_byte_length": 0,
        "body_sha256": "0" * 64,
        "network_executed": True,
        "execution_digest": "0" * 64,
        "unexpected": True,
    }

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        CeqanetCsvExportExecution.model_validate(payload)
