import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_vocabulary_export_cli import app

runner = CliRunner()


def _advanced_search_html() -> str:
    return """
    <html>
      <body>
        <select name="DocumentType">
          <option value="">(Any)</option>
          <option>EIR - Draft EIR</option>
        </select>
        <select name="LeadAgency">
          <option value="">(Any)</option>
          <option>Redlands, City of</option>
          <option>Riverside County Transportation Commission</option>
          <option>ACE Charter School</option>
        </select>
        <select name="County">
          <option>San Bernardino</option>
          <option>Riverside</option>
        </select>
      </body>
    </html>
    """


def _execution_json(path: Path) -> None:
    html = _advanced_search_html()
    payload = {
        "metadata": {"schema_version": "ceqanet_listing_execution.v1"},
        "snapshots": [
            {
                "page_number": 1,
                "request_url": "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
                "final_url": "https://ceqanet.lci.ca.gov/Search?County=San+Bernardino",
                "status_code": 200,
                "content_type": "text/html; charset=utf-8",
                "body_text": html,
                "body_length": len(html),
                "body_truncated": False,
                "executed": True,
                "reachable": True,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_vocabulary_export_cli_emits_execution_snapshot_json(tmp_path: Path) -> None:
    input_path = tmp_path / "execution.json"
    _execution_json(input_path)

    result = runner.invoke(
        app,
        ["export", "--input", str(input_path), "--json-output"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_search_vocabulary.v1"
    assert payload["metadata"]["input"]["input_format"] == "execution-json"
    assert payload["metadata"]["input"]["snapshot"]["status_code"] == 200
    assert payload["metadata"]["counts"] == {
        "DocumentType": 2,
        "LeadAgency": 4,
        "County": 2,
    }
    assert payload["metadata"]["lead_agency_type_counts"] == {
        "charter_school": 1,
        "city": 1,
        "transportation_agency": 1,
    }
    assert payload["vocabulary"]["LeadAgency"][1]["agency_type"] == "city"


def test_ceqanet_vocabulary_export_cli_writes_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "advanced.html"
    output_path = tmp_path / "vocabulary.json"
    input_path.write_text(_advanced_search_html(), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "export",
            "--input",
            str(input_path),
            "--input-format",
            "html",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet search vocabulary JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["input"]["input_format"] == "html"
    assert payload["metadata"]["group_count"] == 3


def test_ceqanet_vocabulary_export_cli_renders_summary_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "advanced.html"
    input_path.write_text(_advanced_search_html(), encoding="utf-8")

    result = runner.invoke(app, ["export", "--input", str(input_path)])

    assert result.exit_code == 0
    assert "CEQAnet Search Vocabulary" in result.output
    assert "DocumentType" in result.output
    assert "Lead/Public Agency Type Counts" in result.output


def test_ceqanet_vocabulary_export_cli_rejects_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "advanced.html"
    output_path = tmp_path / "vocabulary.json"
    input_path.write_text(_advanced_search_html(), encoding="utf-8")

    result = runner.invoke(
        app,
        ["export", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_vocabulary_export_cli_rejects_bad_snapshot_index(tmp_path: Path) -> None:
    input_path = tmp_path / "execution.json"
    _execution_json(input_path)

    result = runner.invoke(
        app,
        [
            "export",
            "--input",
            str(input_path),
            "--snapshot-index",
            "1",
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "snapshot-index must be between 0 and 0" in result.output
