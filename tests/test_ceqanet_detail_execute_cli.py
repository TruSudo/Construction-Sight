import json
from pathlib import Path

from typer.testing import CliRunner

import constructionsight.ceqanet_detail_execute_cli as cli

runner = CliRunner()


class _FakeResponse:
    status_code = 200
    text = "<html><body><h1>Project Details</h1><p>SCH Number 2017101033</p></body></html>"
    url = "https://ceqanet.lci.ca.gov/Project/2017101033"
    headers = {"content-type": "text/html; charset=utf-8"}


def test_ceqanet_detail_execute_cli_writes_json_output(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "detail-execution.json"

    def fake_get(
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
        headers: dict[str, str],
    ) -> _FakeResponse:
        assert url == "https://ceqanet.lci.ca.gov/Project/2017101033"
        assert follow_redirects is True
        assert timeout == 20.0
        assert headers["User-Agent"] == "ConstructionSight/0.1"
        return _FakeResponse()

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            "https://ceqanet.lci.ca.gov/Project/2017101033",
            "--execute-live",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet detail execution JSON" in result.output

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["schema_version"] == "ceqanet_detail_execution.v1"
    assert payload["metadata"]["allowed"] is True
    assert payload["metadata"]["executed_request_count"] == 1
    assert payload["metadata"]["successful_response_count"] == 1
    assert len(payload["snapshots"]) == 1
    assert payload["snapshots"][0]["request_url"] == "https://ceqanet.lci.ca.gov/Project/2017101033"
    assert payload["snapshots"][0]["reachable"] is True
    assert payload["snapshots"][0]["body_truncated"] is False


def test_ceqanet_detail_execute_cli_renders_summary(tmp_path: Path, monkeypatch) -> None:
    def fake_get(
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
        headers: dict[str, str],
    ) -> _FakeResponse:
        return _FakeResponse()

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            "https://ceqanet.lci.ca.gov/Project/2017101033",
            "--execute-live",
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Detail Execution" in result.output
    assert "Bounded Detail Snapshot" in result.output


def test_ceqanet_detail_execute_cli_rejects_without_live_consent() -> None:
    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            "https://ceqanet.lci.ca.gov/Project/2017101033",
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "Refusing live execution without --execute-live" in result.output


def test_ceqanet_detail_execute_cli_rejects_output_without_json(tmp_path: Path) -> None:
    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            "https://ceqanet.lci.ca.gov/Project/2017101033",
            "--execute-live",
            "--output",
            str(tmp_path / "detail-execution.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_detail_execute_cli_rejects_non_ceqanet_url() -> None:
    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            "https://example.com/Project/2017101033",
            "--execute-live",
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "--url must target ceqanet.lci.ca.gov" in result.output


def test_ceqanet_detail_execute_cli_truncates_large_body(tmp_path: Path, monkeypatch) -> None:
    output_path = tmp_path / "detail-execution.json"

    class LargeResponse:
        status_code = 200
        text = "abcdef"
        url = "https://ceqanet.lci.ca.gov/Project/2017101033"
        headers = {"content-type": "text/html; charset=utf-8"}

    def fake_get(
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
        headers: dict[str, str],
    ) -> LargeResponse:
        return LargeResponse()

    monkeypatch.setattr(cli.httpx, "get", fake_get)

    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            "https://ceqanet.lci.ca.gov/Project/2017101033",
            "--execute-live",
            "--max-body-chars",
            "3",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    snapshot = payload["snapshots"][0]
    assert snapshot["body_text"] == "abc"
    assert snapshot["body_length"] == 6
    assert snapshot["body_truncated"] is True
