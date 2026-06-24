import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_operator_report_cli import app

runner = CliRunner()


def _operator_package(path: Path) -> None:
    payload = {
        "metadata": {
            "schema_version": "ceqanet_operator_package.v1",
            "result_record_count": 1,
            "ceqa_record_count": 1,
            "site_count": 1,
            "entity_count": 1,
            "operation_count": 1,
            "warning_count": 0,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "persistence_preview": {
            "metadata": {"schema_version": "ceqanet_persistence_preview.v1"},
            "ceqa_records": [
                {
                    "ceqa_key": "ceqa:ceqanet:2017101033",
                    "title": "Countywide Plan",
                    "state_clearinghouse_number": "2017101033",
                    "county": "San Bernardino",
                    "lead_agency": "County Agency",
                }
            ],
        },
        "write_plan": {
            "metadata": {"schema_version": "ceqanet_write_plan.v1"},
            "operations": [
                {
                    "operation_id": "ceqa_records:ceqa:ceqanet:2017101033",
                    "action": "upsert_preview",
                    "target_collection": "ceqa_records",
                    "target_key": "ceqa:ceqanet:2017101033",
                }
            ],
        },
        "warnings": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_operator_report_cli_prints_markdown(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
        ],
    )

    assert result.exit_code == 0
    assert "# CEQAnet Operator Report" in result.output
    assert "Countywide Plan" in result.output


def test_ceqanet_operator_report_cli_writes_markdown_output(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    output_path = tmp_path / "operator-report.md"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator Markdown report" in result.output
    markdown = output_path.read_text(encoding="utf-8")
    assert "# CEQAnet Operator Report" in markdown
    assert "ceqa_records:ceqa:ceqanet:2017101033" in markdown


def test_ceqanet_operator_report_cli_emits_json(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_operator_report.v1"
    assert payload["metadata"]["input"]["operator_package_path"] == str(package_path)
    assert payload["metadata"]["operation_count"] == 1
    assert "# CEQAnet Operator Report" in payload["markdown"]


def test_ceqanet_operator_report_cli_writes_json_output(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    output_path = tmp_path / "operator-report.json"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--json-output-path",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator report JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["operation_count"] == 1


def test_ceqanet_operator_report_cli_rejects_bad_package(tmp_path: Path) -> None:
    package_path = tmp_path / "bad-package.json"
    package_path.write_text(json.dumps({"metadata": {"schema_version": "wrong.v1"}}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "ceqanet_operator_package.v1" in result.output
