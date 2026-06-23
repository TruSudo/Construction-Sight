import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_listing_execute_cli import app

runner = CliRunner()


def test_ceqanet_listing_execute_cli_requires_explicit_live_consent() -> None:
    result = runner.invoke(app, ["execute", "--county", "San Bernardino"])

    assert result.exit_code != 0
    assert "Refusing live execution without --execute-live" in result.output


def test_ceqanet_listing_execute_cli_blocks_without_network_when_access_policy_blocks() -> None:
    result = runner.invoke(
        app,
        [
            "execute",
            "--county",
            "San Bernardino",
            "--has-captcha",
            "--execute-live",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_listing_execution.v1"
    assert payload["metadata"]["allowed"] is False
    assert payload["metadata"]["access"]["decision"] == "blocked"
    assert payload["metadata"]["planned_request_count"] == 0
    assert payload["metadata"]["executed_request_count"] == 0
    assert payload["metadata"]["successful_response_count"] == 0
    assert payload["metadata"]["failed_response_count"] == 0
    assert payload["snapshots"] == []
    assert "captcha" in payload["metadata"]["reason"]


def test_ceqanet_listing_execute_cli_writes_blocked_json_output(tmp_path: Path) -> None:
    output_path = tmp_path / "execution.json"

    result = runner.invoke(
        app,
        [
            "execute",
            "--county",
            "Riverside",
            "--robots-disallows-collection",
            "--execute-live",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet listing execution JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["allowed"] is False
    assert payload["metadata"]["query"]["counties"] == ["Riverside"]
    assert payload["snapshots"] == []


def test_ceqanet_listing_execute_cli_rejects_output_without_json(tmp_path: Path) -> None:
    output_path = tmp_path / "execution.json"

    result = runner.invoke(
        app,
        [
            "execute",
            "--county",
            "San Bernardino",
            "--execute-live",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_listing_execute_cli_rejects_unbounded_query_even_with_live_consent() -> None:
    result = runner.invoke(app, ["execute", "--execute-live"])

    assert result.exit_code != 0
    assert "requires at least one bounding query filter" in result.output
