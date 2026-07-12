import json
from pathlib import Path

from click import unstyle
from typer.testing import CliRunner

from constructionsight.ceqanet_listing_plan_cli import app

runner = CliRunner()


def test_ceqanet_listing_dry_run_cli_renders_request_evidence_table() -> None:
    result = runner.invoke(
        app,
        [
            "dry-run",
            "--county",
            "San Bernardino",
            "--document-type",
            "EIR",
            "--page-size",
            "50",
            "--max-pages",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Listing Dry Run" in result.output
    assert "Dry-Run Request Evidence" in result.output
    assert "Planned requests" in result.output
    assert "Executed requests" in result.output
    assert "False" in result.output
    assert "San+Bernardino" in result.output
    assert "DocumentType=EIR+-+Draft+EIR" in result.output


def test_ceqanet_listing_dry_run_cli_rejects_unsupported_text_filter() -> None:
    result = runner.invoke(
        app,
        [
            "dry-run",
            "--county",
            "San Bernardino",
            "--text",
            "warehouse",
        ],
    )

    assert result.exit_code != 0
    assert "text_terms are unsupported by the verified search contract" in unstyle(
        result.output
    )


def test_ceqanet_listing_dry_run_cli_emits_json_request_evidence() -> None:
    result = runner.invoke(
        app,
        [
            "dry-run",
            "--lead-agency",
            "City of Fontana",
            "--received-from",
            "2026-01-01",
            "--received-to",
            "2026-01-31",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_listing_dry_run.v1"
    assert payload["metadata"]["allowed"] is True
    assert payload["metadata"]["planned_request_count"] == 1
    assert payload["metadata"]["executed_request_count"] == 0
    assert payload["metadata"]["downloads_documents"] is False
    assert payload["metadata"]["mutates_remote_state"] is False
    assert payload["metadata"]["query"]["lead_agencies"] == ["City of Fontana"]
    assert payload["requests"][0]["method"] == "GET"
    assert payload["requests"][0]["executed"] is False
    assert "StartRange=2026-01-01" in payload["requests"][0]["url"]


def test_ceqanet_listing_dry_run_cli_blocks_when_access_policy_blocks() -> None:
    result = runner.invoke(
        app,
        [
            "dry-run",
            "--county",
            "San Bernardino",
            "--has-captcha",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["allowed"] is False
    assert payload["metadata"]["access"]["decision"] == "blocked"
    assert payload["metadata"]["planned_request_count"] == 0
    assert payload["metadata"]["executed_request_count"] == 0
    assert payload["metadata"]["maximum_records"] == 0
    assert payload["requests"] == []
    assert "captcha" in payload["metadata"]["reason"]


def test_ceqanet_listing_dry_run_cli_writes_json_output(tmp_path: Path) -> None:
    output_path = tmp_path / "dry-run.json"

    result = runner.invoke(
        app,
        [
            "dry-run",
            "--county",
            "Riverside",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet listing dry-run JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["query"]["counties"] == ["Riverside"]
    assert payload["requests"][0]["url"].endswith("County=Riverside")


def test_ceqanet_listing_dry_run_cli_rejects_output_without_json(tmp_path: Path) -> None:
    output_path = tmp_path / "dry-run.json"

    result = runner.invoke(
        app,
        [
            "dry-run",
            "--county",
            "San Bernardino",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_listing_dry_run_cli_rejects_unbounded_query() -> None:
    result = runner.invoke(app, ["dry-run"])

    assert result.exit_code != 0
    assert "requires at least one bounding query filter" in result.output
