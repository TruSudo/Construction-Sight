import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_persistence_execute_cli import app

runner = CliRunner()


def _plan(path: Path) -> None:
    payload = {
        "metadata": {"schema_version": "ceqanet_write_plan.v1"},
        "operations": [
            {
                "operation_id": "sites:site:ceqanet:2017101033",
                "action": "upsert_preview",
                "target_collection": "sites",
                "target_key": "site:ceqanet:2017101033",
                "source_index": 0,
                "payload": {
                    "site_key": "site:ceqanet:2017101033",
                    "county": "San Bernardino",
                },
            },
            {
                "operation_id": "entities:entity:ceqanet:lead-agency:san-bernardino-county",
                "action": "upsert_preview",
                "target_collection": "entities",
                "target_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                "source_index": 0,
                "payload": {
                    "entity_key": "entity:ceqanet:lead-agency:san-bernardino-county",
                    "name": "San Bernardino County",
                    "role": "agency",
                },
            },
            {
                "operation_id": "ceqa_records:ceqa:ceqanet:2017101033",
                "action": "upsert_preview",
                "target_collection": "ceqa_records",
                "target_key": "ceqa:ceqanet:2017101033",
                "source_index": 0,
                "payload": {
                    "ceqa_key": "ceqa:ceqanet:2017101033",
                    "title": "San Bernardino Countywide Plan",
                    "state_clearinghouse_number": "2017101033",
                },
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_persistence_cli_json_output(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    db_path = tmp_path / "construction.sqlite3"
    _plan(plan_path)

    result = runner.invoke(
        app,
        [
            "execute",
            "--write-plan",
            str(plan_path),
            "--database-path",
            str(db_path),
            "--execute-write",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_persistence_execution.v1"
    assert payload["metadata"]["applied_count"] == 3
    assert payload["metadata"]["database_opened"] is True
    assert payload["metadata"]["persistence_mutated"] is True
    assert db_path.exists()


def test_ceqanet_persistence_cli_refuses_without_consent(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    db_path = tmp_path / "construction.sqlite3"
    _plan(plan_path)

    result = runner.invoke(
        app,
        [
            "execute",
            "--write-plan",
            str(plan_path),
            "--database-path",
            str(db_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "Refusing persistence execution without --execute-write" in result.output
    assert not db_path.exists()


def test_ceqanet_persistence_cli_requires_json_for_file_output(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    db_path = tmp_path / "construction.sqlite3"
    _plan(plan_path)

    result = runner.invoke(
        app,
        [
            "execute",
            "--write-plan",
            str(plan_path),
            "--database-path",
            str(db_path),
            "--execute-write",
            "--output",
            str(tmp_path / "out.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_persistence_cli_requires_database_target(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    _plan(plan_path)

    result = runner.invoke(
        app,
        [
            "execute",
            "--write-plan",
            str(plan_path),
            "--execute-write",
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "target database" in result.output
