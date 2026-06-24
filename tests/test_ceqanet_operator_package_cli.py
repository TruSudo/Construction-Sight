import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_operator_package_cli import app

runner = CliRunner()


def _chain_report(path: Path) -> None:
    payload = {
        "metadata": {
            "schema_version": "ceqanet_chain_report.v1",
            "result_record_count": 1,
            "missing_detail_count": 0,
            "sch_mismatch_count": 0,
            "network_executed": False,
            "persistence_mutated": False,
        },
        "enrichment": {
            "metadata": {"schema_version": "ceqanet_detail_enrichment.v1"},
            "records": [
                {
                    "title": "Countywide Plan",
                    "detail_url": "https://ceqanet.lci.ca.gov/Project/2017101033",
                    "sch_number": "2017101033",
                    "document_type": "Environmental Impact Report",
                    "lead_agency": "County Agency",
                    "county": "San Bernardino",
                    "city": "San Bernardino",
                    "project_location": "San Bernardino County, California",
                    "project_description": "Countywide policy plan.",
                    "source_url": "https://ceqanet.lci.ca.gov/Search",
                    "raw_result_text": "SCH Number 2017101033",
                    "raw_detail_text": "Project Title Countywide Plan",
                    "title_source": "human_label",
                    "has_human_title": True,
                    "requires_detail_enrichment": False,
                    "enrichment_status": "enriched",
                    "field_sources": {"title": "detail_page"},
                    "warnings": [],
                }
            ],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_operator_package_cli_emits_json(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_operator_package.v1"
    assert payload["metadata"]["input"]["chain_report_path"] == str(chain_path)
    assert payload["metadata"]["ceqa_record_count"] == 1
    assert payload["metadata"]["operation_count"] == 3
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False
    assert payload["write_plan"]["metadata"]["operation_count"] == 3


def test_ceqanet_operator_package_cli_writes_json_output(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.json"
    output_path = tmp_path / "package.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator package JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["operation_count"] == 3


def test_ceqanet_operator_package_cli_rejects_output_without_json(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--output",
            str(tmp_path / "package.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_operator_package_cli_rejects_bad_chain_report(tmp_path: Path) -> None:
    chain_path = tmp_path / "bad-chain.json"
    chain_path.write_text(
        json.dumps({"metadata": {"schema_version": "wrong.v1"}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "ceqanet_chain_report.v1" in result.output
