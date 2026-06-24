import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_write_plan_cli import app

runner = CliRunner()


def _preview_payload(path: Path) -> None:
    payload = {
        "metadata": {
            "schema_version": "ceqanet_persistence_preview.v1",
            "ceqa_record_count": 1,
            "site_count": 1,
            "entity_count": 1,
            "skipped_record_count": 0,
            "planned_write_count": 3,
            "network_executed": False,
            "persistence_mutated": False,
        },
        "ceqa_records": [
            {
                "ceqa_key": "ceqa:ceqanet:2017101033",
                "title": "San Bernardino Countywide Plan",
                "state_clearinghouse_number": "2017101033",
            }
        ],
        "sites": [
            {
                "site_key": "site:ceqanet:2017101033",
                "county": "San Bernardino",
            }
        ],
        "entities": [
            {
                "entity_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                "name": "San Bernardino County",
                "role": "agency",
            }
        ],
        "skipped_records": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_write_plan_cli_emits_json(tmp_path: Path) -> None:
    preview_path = tmp_path / "preview.json"
    _preview_payload(preview_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--persistence-preview",
            str(preview_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_write_plan.v1"
    assert payload["metadata"]["input"]["persistence_preview_path"] == str(preview_path)
    assert payload["metadata"]["operation_count"] == 3
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False
    assert payload["operations"][0]["target_collection"] == "ceqa_records"


def test_ceqanet_write_plan_cli_writes_json_output(tmp_path: Path) -> None:
    preview_path = tmp_path / "preview.json"
    output_path = tmp_path / "write-plan.json"
    _preview_payload(preview_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--persistence-preview",
            str(preview_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet write plan JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["operation_count"] == 3
    assert payload["operations"][1]["target_collection"] == "sites"


def test_ceqanet_write_plan_cli_renders_summary(tmp_path: Path) -> None:
    preview_path = tmp_path / "preview.json"
    _preview_payload(preview_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--persistence-preview",
            str(preview_path),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Write Plan Preview" in result.output
    assert "Planned Operations" in result.output


def test_ceqanet_write_plan_cli_rejects_output_without_json(tmp_path: Path) -> None:
    preview_path = tmp_path / "preview.json"
    _preview_payload(preview_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--persistence-preview",
            str(preview_path),
            "--output",
            str(tmp_path / "write-plan.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_write_plan_cli_rejects_bad_preview(tmp_path: Path) -> None:
    preview_path = tmp_path / "bad-preview.json"
    preview_path.write_text(json.dumps({"metadata": {"schema_version": "wrong.v1"}}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "build",
            "--persistence-preview",
            str(preview_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "schema_version must be ceqanet_persistence_preview.v1" in result.output
