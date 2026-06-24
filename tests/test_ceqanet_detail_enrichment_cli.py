import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_detail_enrichment_cli import app

runner = CliRunner()


def _result_parse(path: Path) -> None:
    payload = {
        "metadata": {
            "schema_version": "ceqanet_result_page_parse.v1",
            "record_count": 1,
            "detail_enrichment_required_count": 1,
        },
        "records": [
            {
                "title": "2026061234",
                "detail_url": "https://ceqanet.lci.ca.gov/Project/2026061234",
                "sch_number": "2026061234",
                "document_type": None,
                "lead_agency": None,
                "county": "San Bernardino",
                "city": None,
                "source_url": "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
                "raw_text": "SCH Number | 2026061234",
                "title_source": "sch_number",
                "requires_detail_enrichment": True,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _detail_parse(path: Path) -> None:
    payload = {
        "metadata": {
            "schema_version": "ceqanet_detail_page_parse.v1",
            "has_human_title": True,
            "label_count": 4,
            "link_count": 2,
        },
        "detail": {
            "title": "Fontana Warehouse Project",
            "title_source": "human_label",
            "sch_number": "2026061234",
            "document_type": None,
            "lead_agency": "Fontana, City of",
            "county": "San Bernardino",
            "city": "Fontana",
            "project_location": "Fontana, California",
            "project_description": "Warehouse and site improvements.",
            "contact": "Planning Department",
            "raw_text": "Project Title | Fontana Warehouse Project",
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_detail_enrichment_cli_emits_json(tmp_path: Path) -> None:
    result_path = tmp_path / "results.json"
    detail_path = tmp_path / "detail.json"
    _result_parse(result_path)
    _detail_parse(detail_path)

    result = runner.invoke(
        app,
        [
            "enrich",
            "--result-parse",
            str(result_path),
            "--detail-parse",
            str(detail_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_detail_enrichment.v1"
    assert payload["metadata"]["record_count"] == 1
    assert payload["metadata"]["enriched_count"] == 1
    assert payload["metadata"]["missing_detail_count"] == 0
    assert payload["metadata"]["input"]["detail_parse_count"] == 1
    assert payload["records"][0]["title"] == "Fontana Warehouse Project"
    assert payload["records"][0]["lead_agency"] == "Fontana, City of"
    assert payload["records"][0]["requires_detail_enrichment"] is False
    assert payload["records"][0]["field_sources"]["title"] == "detail_page"


def test_ceqanet_detail_enrichment_cli_writes_json_output(tmp_path: Path) -> None:
    result_path = tmp_path / "results.json"
    detail_path = tmp_path / "detail.json"
    output_path = tmp_path / "enrichment.json"
    _result_parse(result_path)
    _detail_parse(detail_path)

    result = runner.invoke(
        app,
        [
            "enrich",
            "--result-parse",
            str(result_path),
            "--detail-parse",
            str(detail_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet detail enrichment JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["enriched_count"] == 1
    assert payload["records"][0]["project_description"] == "Warehouse and site improvements."


def test_ceqanet_detail_enrichment_cli_renders_summary_without_json(tmp_path: Path) -> None:
    result_path = tmp_path / "results.json"
    detail_path = tmp_path / "detail.json"
    _result_parse(result_path)
    _detail_parse(detail_path)

    result = runner.invoke(
        app,
        [
            "enrich",
            "--result-parse",
            str(result_path),
            "--detail-parse",
            str(detail_path),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Detail Enrichment" in result.output
    assert "Enriched Records" in result.output
    assert "Fontana Warehouse Project" in result.output
    assert "human_label" in result.output


def test_ceqanet_detail_enrichment_cli_rejects_output_without_json(tmp_path: Path) -> None:
    result_path = tmp_path / "results.json"
    output_path = tmp_path / "enrichment.json"
    _result_parse(result_path)

    result = runner.invoke(
        app,
        [
            "enrich",
            "--result-parse",
            str(result_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_detail_enrichment_cli_allows_missing_detail_parse(tmp_path: Path) -> None:
    result_path = tmp_path / "results.json"
    _result_parse(result_path)

    result = runner.invoke(
        app,
        [
            "enrich",
            "--result-parse",
            str(result_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["enriched_count"] == 0
    assert payload["metadata"]["missing_detail_count"] == 1
    assert payload["records"][0]["enrichment_status"] == "missing_detail"
    assert payload["records"][0]["title"] == "2026061234"


def test_ceqanet_detail_enrichment_cli_rejects_result_without_records(tmp_path: Path) -> None:
    result_path = tmp_path / "bad-results.json"
    result_path.write_text(json.dumps({"metadata": {}}), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "enrich",
            "--result-parse",
            str(result_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "must contain a records list" in result.output
