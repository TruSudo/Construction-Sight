import json
import re
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_listing_plan_cli import app

runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    return " ".join(_ANSI_ESCAPE.sub("", text).split())


def test_ceqanet_listing_plan_cli_renders_allowed_plan_table() -> None:
    result = runner.invoke(
        app,
        [
            "plan",
            "--county",
            "San Bernardino",
            "--document-type",
            "EIR",
            "--high-signal-only",
            "--page-size",
            "50",
            "--max-pages",
            "2",
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Read-Only Listing Plan" in result.output
    assert "Allowed" in result.output
    assert "True" in result.output
    assert "Planned GET Requests" in result.output
    assert "County=San Bernardino" in result.output
    assert "DocumentType=EIR - Draft EIR" in result.output


def test_ceqanet_listing_plan_cli_rejects_unsupported_text_filter() -> None:
    result = runner.invoke(
        app,
        [
            "plan",
            "--county",
            "San Bernardino",
            "--text",
            "warehouse",
        ],
    )

    assert result.exit_code != 0
    assert "text_terms are unsupported by the verified search contract" in _plain(
        result.output
    )


def test_ceqanet_listing_plan_cli_emits_json_allowed_plan() -> None:
    result = runner.invoke(
        app,
        [
            "plan",
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
    assert payload["metadata"]["schema_version"] == "ceqanet_listing_plan.v1"
    assert payload["metadata"]["allowed"] is True
    assert payload["metadata"]["maximum_records"] == 25
    assert payload["metadata"]["query"]["lead_agencies"] == ["City of Fontana"]
    assert payload["pages"][0]["method"] == "GET"
    assert payload["pages"][0]["downloads_documents"] is False
    assert payload["pages"][0]["mutates_remote_state"] is False


def test_ceqanet_listing_plan_cli_blocks_when_access_policy_blocks() -> None:
    result = runner.invoke(
        app,
        [
            "plan",
            "--county",
            "San Bernardino",
            "--robots-disallows-collection",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["allowed"] is False
    assert payload["metadata"]["access"]["decision"] == "blocked"
    assert payload["metadata"]["maximum_records"] == 0
    assert payload["pages"] == []
    assert "Robots policy disallows" in payload["metadata"]["reason"]


def test_ceqanet_listing_plan_cli_writes_json_output(tmp_path: Path) -> None:
    output_path = tmp_path / "listing-plan.json"

    result = runner.invoke(
        app,
        [
            "plan",
            "--county",
            "Riverside",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet listing plan JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["query"]["counties"] == ["Riverside"]
    assert payload["pages"][0]["params"][0] == {
        "name": "County",
        "value": "Riverside",
    }


def test_ceqanet_listing_plan_cli_rejects_output_without_json(tmp_path: Path) -> None:
    output_path = tmp_path / "listing-plan.json"

    result = runner.invoke(
        app,
        [
            "plan",
            "--county",
            "San Bernardino",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_listing_plan_cli_rejects_unbounded_query() -> None:
    result = runner.invoke(app, ["plan"])

    assert result.exit_code != 0
    assert "requires at least one bounding query filter" in result.output


def test_ceqanet_listing_plan_cli_rejects_reversed_date_range() -> None:
    result = runner.invoke(
        app,
        [
            "plan",
            "--county",
            "San Bernardino",
            "--received-from",
            "2026-02-01",
            "--received-to",
            "2026-01-01",
        ],
    )

    assert result.exit_code != 0
    assert "received_from must be on or before received_to" in result.output
