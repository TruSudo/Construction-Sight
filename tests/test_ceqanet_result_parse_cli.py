import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_result_parse_cli import app

runner = CliRunner()


def _result_html() -> str:
    return """
    <html>
      <body>
        <div class="search-result">
          <a href="/Project/2026061234">Fontana Warehouse Project</a>
          <span>SCH Number</span><span>2026061234</span>
          <span>Lead Agency</span><span>Fontana, City of</span>
          <span>County</span><span>San Bernardino</span>
        </div>
      </body>
    </html>
    """


def _execution_json(path: Path) -> None:
    html = _result_html()
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


def test_ceqanet_result_parse_cli_emits_execution_snapshot_json(tmp_path: Path) -> None:
    input_path = tmp_path / "execution.json"
    _execution_json(input_path)

    result = runner.invoke(app, ["parse", "--input", str(input_path), "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_result_page_parse.v1"
    assert payload["metadata"]["record_count"] == 1
    assert payload["metadata"]["input"]["input_format"] == "execution-json"
    assert payload["metadata"]["input"]["snapshot"]["status_code"] == 200
    assert payload["metadata"]["detail_enrichment_required_count"] == 0
    assert payload["records"][0]["title"] == "Fontana Warehouse Project"
    assert payload["records"][0]["title_source"] == "human_link_text"
    assert payload["records"][0]["requires_detail_enrichment"] is False


def test_ceqanet_result_parse_cli_writes_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "results.html"
    output_path = tmp_path / "parsed.json"
    input_path.write_text(_result_html(), encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "parse",
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
    assert "Wrote CEQAnet result parse JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["record_count"] == 1


def test_ceqanet_result_parse_cli_renders_summary_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "results.html"
    input_path.write_text(_result_html(), encoding="utf-8")

    result = runner.invoke(app, ["parse", "--input", str(input_path)])

    assert result.exit_code == 0
    assert "CEQAnet Result Page Parse" in result.output
    assert "Detail enrichment required" in result.output
    assert "Title Source" in result.output
    assert "Needs Detail" in result.output
    assert "Fontana Warehouse Project" in result.output
    assert "human_link_text" in result.output


def test_ceqanet_result_parse_cli_rejects_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "results.html"
    output_path = tmp_path / "parsed.json"
    input_path.write_text(_result_html(), encoding="utf-8")

    result = runner.invoke(
        app,
        ["parse", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_result_parse_cli_rejects_bad_snapshot_index(tmp_path: Path) -> None:
    input_path = tmp_path / "execution.json"
    _execution_json(input_path)

    result = runner.invoke(
        app,
        [
            "parse",
            "--input",
            str(input_path),
            "--snapshot-index",
            "1",
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "snapshot-index must be between 0 and 0" in result.output
