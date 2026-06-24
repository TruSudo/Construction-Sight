import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_persistence_preview_cli import app

runner = CliRunner()


def _chain_report(path: Path) -> None:
    payload = {
        "metadata": {"schema_version": "ceqanet_chain_report.v1"},
        "enrichment": {
            "metadata": {"schema_version": "ceqanet_detail_enrichment.v1"},
            "records": [
                {
                    "title": "San Bernardino Countywide Plan",
                    "detail_url": "https://ceqanet.lci.ca.gov/Project/2017101033",
                    "sch_number": "2017101033",
                    "document_type": "Environmental Impact Report",
                    "lead_agency": "San Bernardino County",
                    "county": "San Bernardino",
                    "city": "San Bernardino",
                    "project_location": "San Bernardino County, California",
                    "project_description": "Countywide policy plan.",
                    "source_url": "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
                    "raw_result_text": "SCH Number 2017101033",
                    "raw_detail_text": "Project Title San Bernardino Countywide Plan",
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


def test_ceqanet_persistence_preview_cli_emits_json(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "preview",
            "--chain-report",
            str(chain_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_persistence_preview.v1"
    assert payload["metadata"]["input"]["chain_report_path"] == str(chain_path)
    assert payload["metadata"]["ceqa_record_count"] == 1
    assert payload["metadata"]["planned_write_count"] == 3
    assert payload["metadata"]["persistence_mutated"] is False
    assert payload["ceqa_records"][0]["ceqa_key"] == "ceqa:ceqanet:2017101033"


def test_ceqanet_persistence_preview_cli_writes_json_output(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.json"
    output_path = tmp_path / "preview.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "preview",
            "--chain-report",
            str(chain_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet persistence preview JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["ceqa_record_count"] == 1
    assert payload["sites"][0]["site_key"] == "site:ceqanet:2017101033"


def test_ceqanet_persistence_preview_cli_renders_summary(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "preview",
            "--chain-report",
            str(chain_path),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Persistence Preview" in result.output
    assert "CEQA Record Preview" in result.output


def test_ceqanet_persistence_preview_cli_rejects_output_without_json(tmp_path: Path) -> None:
    chain_path = tmp_path / "chain.json"
    _chain_report(chain_path)

    result = runner.invoke(
        app,
        [
            "preview",
            "--chain-report",
            str(chain_path),
            "--output",
            str(tmp_path / "preview.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_persistence_preview_cli_rejects_bad_chain_report(tmp_path: Path) -> None:
    chain_path = tmp_path / "bad-chain.json"
    chain_path.write_text(json.dumps({"metadata": {}}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "preview",
            "--chain-report",
            str(chain_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "must contain an enrichment object" in result.output
