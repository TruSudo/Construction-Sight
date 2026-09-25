import json
from pathlib import Path

from typer.testing import CliRunner

import constructionsight.ceqanet_detail_execute_cli as cli

runner = CliRunner()
_URL = "https://ceqanet.lci.ca.gov/Project/2017101033"


def _payload(
    *,
    body_text: str = "detail",
    body_length: int = 6,
    truncated: bool = False,
) -> dict[str, object]:
    return {
        "metadata": {
            "schema_version": "ceqanet_detail_execution.v2",
            "allowed": True,
            "reason": "synthetic authorized detail execution",
            "requested_url": _URL,
            "executed_request_count": 1,
            "successful_response_count": 1,
            "failed_response_count": 0,
            "authorization": {
                "actor_id": "operator:test",
                "decision_id": "authorization-decision:" + ("d" * 64),
                "preflight_id": "authorization-preflight:" + ("p" * 64),
                "valid_until": "2026-07-15T12:05:00+00:00",
            },
        },
        "snapshots": [
            {
                "request_url": _URL,
                "final_url": _URL,
                "status_code": 200,
                "reachable": True,
                "failure_kind": "none",
                "body_text": body_text,
                "body_length": body_length,
                "body_truncated": truncated,
                "attempt_count": 1,
            }
        ],
    }


def test_ceqanet_detail_execute_cli_writes_json_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "detail-execution.json"
    calls: list[dict[str, object]] = []

    def fake_execute(**kwargs):
        calls.append(kwargs)
        return _payload()

    monkeypatch.setattr(cli, "execute_authorized_ceqanet_detail", fake_execute)
    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            _URL,
            "--operator-id",
            "operator:test",
            "--authorization-reason",
            "Review one exact detail page.",
            "--access-fact-basis",
            "review:1111111111111111111111111111111111111111111111111111111111111111",
            "--execute-live",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet detail execution JSON" in result.output
    assert calls[0]["detail_url"] == _URL
    assert calls[0]["operator_id"] == "operator:test"
    assert calls[0]["access_profile"].access_fact_basis == "review:1111111111111111111111111111111111111111111111111111111111111111"
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["schema_version"] == "ceqanet_detail_execution.v2"
    assert payload["metadata"]["allowed"] is True
    assert payload["metadata"]["executed_request_count"] == 1
    assert payload["metadata"]["successful_response_count"] == 1
    assert payload["snapshots"][0]["request_url"] == _URL
    assert payload["snapshots"][0]["reachable"] is True


def test_ceqanet_detail_execute_cli_rejects_without_live_consent() -> None:
    result = runner.invoke(cli.app, ["execute", "--url", _URL, "--json-output"])

    assert result.exit_code != 0
    assert "Refusing live execution without --execute-live" in result.output


def test_ceqanet_detail_execute_cli_rejects_output_without_json(
    tmp_path: Path,
) -> None:
    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            _URL,
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
    assert "must target the exact public CEQAnet host" in result.output


def test_ceqanet_detail_execute_cli_forwards_bounded_body_ceiling(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output_path = tmp_path / "detail-execution.json"
    calls: list[dict[str, object]] = []

    def fake_execute(**kwargs):
        calls.append(kwargs)
        return _payload(body_text="abc", body_length=6, truncated=True)

    monkeypatch.setattr(cli, "execute_authorized_ceqanet_detail", fake_execute)
    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            _URL,
            "--execute-live",
            "--max-body-bytes",
            "3",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert calls[0]["max_body_bytes"] == 3
    snapshot = json.loads(output_path.read_text(encoding="utf-8"))["snapshots"][0]
    assert snapshot["body_text"] == "abc"
    assert snapshot["body_length"] == 6
    assert snapshot["body_truncated"] is True


def test_ceqanet_detail_execute_cli_requires_access_fact_basis() -> None:
    result = runner.invoke(
        cli.app,
        [
            "execute",
            "--url",
            _URL,
            "--execute-live",
            "--json-output",
        ],
    )

    assert result.exit_code == 1
    assert "lawful access preflight denied execution" in result.output
    assert "fact basis" in result.output
