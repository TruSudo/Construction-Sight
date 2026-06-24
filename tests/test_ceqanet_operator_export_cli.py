import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_operator_export_cli import app

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


def test_ceqanet_operator_export_cli_renders_summary(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain-report.json"
    export_dir = tmp_path / "operator-export"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--output-dir",
            str(export_dir),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Operator Export" in result.output
    assert (export_dir / "operator-package.json").exists()
    assert (export_dir / "persistence-preview.json").exists()
    assert (export_dir / "write-plan.json").exists()
    assert (export_dir / "operator-report.md").exists()
    assert (export_dir / "manifest.json").exists()


def test_ceqanet_operator_export_cli_emits_json(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain-report.json"
    export_dir = tmp_path / "operator-export"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--output-dir",
            str(export_dir),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_operator_export.v1"
    assert payload["metadata"]["input"]["chain_report_path"] == str(chain_path)
    assert payload["metadata"]["bundle_artifact_count"] == 6
    assert payload["metadata"]["verified_artifact_count"] == 5
    assert payload["metadata"]["verification_passed"] is True
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False


def test_ceqanet_operator_export_cli_writes_json_output(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain-report.json"
    export_dir = tmp_path / "operator-export"
    output_path = tmp_path / "operator-export.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--output-dir",
            str(export_dir),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator export JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["verification_passed"] is True


def test_ceqanet_operator_export_cli_rejects_output_without_json(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain-report.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--output-dir",
            str(tmp_path / "operator-export"),
            "--output",
            str(tmp_path / "operator-export.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_operator_export_cli_rejects_bad_chain_report(tmp_path: Path) -> None:
    chain_path = tmp_path / "bad-chain-report.json"
    chain_path.write_text(json.dumps({"metadata": {"schema_version": "wrong.v1"}}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "build",
            "--chain-report",
            str(chain_path),
            "--output-dir",
            str(tmp_path / "operator-export"),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "ceqanet_chain_report.v1" in result.output
