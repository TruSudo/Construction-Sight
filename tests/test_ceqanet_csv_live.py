from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_cli import app
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_live_service import (
    execute_ceqanet_csv_live_request,
    verify_ceqanet_csv_live_execution,
)
from constructionsight.ceqanet_csv_models import CeqanetCsvExportRequest
from constructionsight.ceqanet_csv_service import build_ceqanet_csv_export_request

ROOT = Path(__file__).resolve().parents[1]
PROJECT_FIXTURE = ROOT / "tests/fixtures/ceqanet/project_export.csv"
runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_RICH_BORDER = str.maketrans("", "", "│╭╮╰╯─")


def _plain_terminal(text: str) -> str:
    without_ansi = _ANSI_ESCAPE.sub("", text)
    without_border = without_ansi.translate(_RICH_BORDER)
    return " ".join(without_border.split())


@dataclass
class _Response:
    status_code: int
    content: bytes
    url: str
    headers: dict[str, str]


class _Client(httpx.Client):
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[tuple[str, float]] = []
        super().__init__(
            transport=httpx.MockTransport(self._handle_request),
            follow_redirects=True,
        )

    def _handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(
            (str(request.url), float(request.extensions["timeout"]["read"]))
        )
        return httpx.Response(
            self.response.status_code,
            content=self.response.content,
            headers=self.response.headers,
            request=request,
        )


def _request() -> CeqanetCsvExportRequest:
    return build_ceqanet_csv_export_request(sch_number="2026030377")


def _successful_execution() -> CeqanetCsvLiveExecution:
    request = _request()
    client = _Client(
        _Response(
            status_code=200,
            content=PROJECT_FIXTURE.read_bytes(),
            url=request.source_url,
            headers={
                "content-type": "text/csv; charset=utf-8",
                "content-disposition": 'attachment; filename="project.csv"',
            },
        )
    )
    with client:
        return execute_ceqanet_csv_live_request(
            request,
            execute_live=True,
            client=client,
            timeout_seconds=12.5,
            max_retained_rows=1,
        )


def test_live_execution_requires_explicit_authorization() -> None:
    with pytest.raises(ValueError, match="explicit live authorization"):
        execute_ceqanet_csv_live_request(_request(), execute_live=False)


def test_live_execution_performs_exactly_one_get_without_redirect_or_retry() -> None:
    request = _request()
    client = _Client(
        _Response(
            status_code=200,
            content=PROJECT_FIXTURE.read_bytes(),
            url=request.source_url,
            headers={"content-type": "text/csv"},
        )
    )

    with client:
        execution = execute_ceqanet_csv_live_request(
            request,
            execute_live=True,
            client=client,
            timeout_seconds=12.5,
        )

    assert client.calls == [(request.source_url, 12.5)]
    assert execution.method == "GET"
    assert execution.retry_count == 0
    assert execution.network_executed is True
    assert execution.documents_downloaded is False
    assert execution.persistence_mutated is False


def test_successful_live_execution_embeds_canonical_offline_inspection() -> None:
    execution = _successful_execution()
    verification = verify_ceqanet_csv_live_execution(execution)

    assert execution.status_code == 200
    assert execution.retained_body_complete is True
    assert execution.retained_body_bytes() == PROJECT_FIXTURE.read_bytes()
    assert execution.inspection is not None
    assert execution.inspection.row_count == 2
    assert execution.inspection.retained_row_count == 1
    execution.assert_integrity()
    assert verification.passed is True
    assert verification.findings == []
    assert verification.inspection_digest == execution.inspection.inspection_digest


def test_http_403_is_terminal_without_body_retention_or_bypass() -> None:
    request = _request()
    execution = execute_ceqanet_csv_live_request(
        request,
        execute_live=True,
        client=_Client(
            _Response(
                status_code=403,
                content=b"Forbidden",
                url=request.source_url,
                headers={"content-type": "text/plain"},
            )
        ),
    )
    verification = verify_ceqanet_csv_live_execution(execution)

    assert execution.status_code == 403
    assert execution.inspection is None
    assert execution.error == "AccessControlStatus"
    assert execution.retry_count == 0
    assert execution.retained_body_bytes() == b""
    assert execution.retained_body_complete is False
    assert verification.passed is False
    assert "live CSV response status is not 200: 403" in verification.findings
    assert any("AccessControlStatus" in item for item in verification.findings)


def test_redirect_is_terminal_and_location_body_is_not_retained() -> None:
    request = _request()
    client = _Client(
        _Response(
            status_code=302,
            content=b"redirect response",
            url=request.source_url,
            headers={"location": "https://example.invalid/"},
        )
    )

    with client:
        execution = execute_ceqanet_csv_live_request(
            request,
            execute_live=True,
            client=client,
        )

    assert client.calls == [(request.source_url, 20.0)]
    assert execution.status_code == 302
    assert execution.error == "RedirectDenied"
    assert execution.retained_body_bytes() == b""
    assert execution.retained_body_complete is False


def test_csv_validation_failure_is_retained_as_evidence() -> None:
    request = _request()
    execution = execute_ceqanet_csv_live_request(
        request,
        execute_live=True,
        client=_Client(
            _Response(
                status_code=200,
                content=b"<html>Forbidden</html>",
                url=request.source_url,
                headers={"content-type": "text/html"},
            )
        ),
    )
    verification = verify_ceqanet_csv_live_execution(execution)

    assert execution.inspection is None
    assert execution.inspection_error is None
    assert execution.error == "UnexpectedMediaType"
    assert execution.retained_body_bytes() == b""
    assert execution.retained_body_complete is False
    assert verification.passed is False
    assert any("UnexpectedMediaType" in finding for finding in verification.findings)


def test_oversized_response_is_not_partially_retained_or_claimed_hashed() -> None:
    request = _request()
    execution = execute_ceqanet_csv_live_request(
        request,
        execute_live=True,
        client=_Client(
            _Response(
                status_code=200,
                content=PROJECT_FIXTURE.read_bytes(),
                url=request.source_url,
                headers={"content-type": "text/csv"},
            )
        ),
        max_body_bytes=1,
    )
    verification = verify_ceqanet_csv_live_execution(execution)

    assert execution.observed_body_byte_length == len(PROJECT_FIXTURE.read_bytes())
    assert execution.retained_body_byte_length == 0
    assert execution.retained_body_complete is False
    assert execution.error == "response_exceeds_max_body_bytes"
    assert verification.passed is False
    assert "live CSV response body was not retained completely" in verification.findings


def test_verifier_rejects_tampered_body_and_digest() -> None:
    execution = _successful_execution()
    tampered = execution.model_copy(
        update={
            "retained_body_base64": base64.b64encode(b"changed").decode("ascii"),
        }
    )
    verification = verify_ceqanet_csv_live_execution(tampered)

    assert verification.passed is False
    assert "CEQAnet CSV live execution digest mismatch" in verification.findings
    assert "retained CSV byte length does not match decoded bytes" in verification.findings
    assert "retained CSV SHA-256 does not match response evidence" in verification.findings


def test_verifier_rejects_final_url_identity_drift() -> None:
    execution = _successful_execution().model_copy(
        update={
            "final_url": "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026070311"
        }
    )
    verification = verify_ceqanet_csv_live_execution(execution)

    assert verification.passed is False
    assert "CEQAnet CSV live execution digest mismatch" in verification.findings
    assert (
        "live CSV final URL does not match the approved request identity"
        in verification.findings
    )


def test_live_model_rejects_unknown_fields() -> None:
    payload: dict[str, Any] = _successful_execution().model_dump(mode="json")
    payload["unexpected"] = True

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        CeqanetCsvLiveExecution.model_validate(payload)


def test_execute_cli_refuses_missing_scope_bound_authorization(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "execute-live",
            "--sch-number",
            "2026030377",
            "--output",
            str(tmp_path / "execution.json"),
        ],
    )

    assert result.exit_code != 0
    assert "caller confirmation is required" in _plain_terminal(result.output)
    assert not (tmp_path / "execution.json").exists()


def test_verify_execution_cli_operates_offline(tmp_path: Path) -> None:
    execution_path = tmp_path / "execution.json"
    verification_path = tmp_path / "verification.json"
    execution_path.write_text(
        json.dumps(_successful_execution().model_dump(mode="json")),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "verify-execution",
            str(execution_path),
            "--output",
            str(verification_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(verification_path.read_text(encoding="utf-8"))
    assert payload["passed"] is True
    assert payload["finding_count"] == 0
