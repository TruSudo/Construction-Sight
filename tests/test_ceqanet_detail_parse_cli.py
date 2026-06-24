import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_detail_parse_cli import app

runner = CliRunner()


def _detail_html() -> str:
    return """
    <html>
      <body>
        <main>
          <h1>Project Details</h1>
          <dl>
            <dt>Project Title</dt><dd>Fontana Warehouse Project</dd>
            <dt>SCH Number</dt><dd>2026061234</dd>
            <dt>Lead Agency</dt><dd>Fontana, City of</dd>
            <dt>County</dt><dd>San Bernardino</dd>
          </dl>
        </main>
      </body>
    </html>
    """


def _execution_json(path: Path) -> None:
    html = _detail_html()
    payload = {
        "metadata": {"schema_version": "ceqanet_detail_execution.v1"},
        "snapshots": [
            {
                "page_number": 1,
                "request_url": "https://ceqanet.lci.ca.gov/Project/2026061234",
                "final_url": "https://ceqanet.lci.ca.gov/Project/2026061234",
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


def test_ceqanet_detail_parse_cli_emits_execution_snapshot_json(tmp_path: Path) -> None:
    input_path = tmp_path / "execution.json"
    _execution_json(input_path)

    result = runner.invoke(app, ["parse", "--input", str(input_path), "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_detail_page_parse.v1"
    assert payload["metadata"]["has_human_title"] is True
    assert payload["metadata"]["input"]["input_format"] == "execution-json"
    assert payload["metadata"]["input"]["snapshot"]["status_code"] == 200
    assert payload["detail"]["title"] == "Fontana Warehouse Project"
    assert payload["detail"]["title_source"] == "human_label"
    assert payload["detail"]["sch_number"] == "2026061234"


def test_ceqanet_detail_parse_cli_writes_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "detail.html"
    output_path = tmp_path / "detail.json"
    input_path.write_text(_detail_html(), encoding="utf-8")

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
    assert "Wrote CEQAnet detail parse JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["has_human_title"] is True
    assert payload["detail"]["lead_agency"] == "Fontana, City of"


def test_ceqanet_detail_parse_cli_renders_summary_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "detail.html"
    input_path.write_text(_detail_html(), encoding="utf-8")

    result = runner.invoke(app, ["parse", "--input", str(input_path)])

    assert result.exit_code == 0
    assert "CEQAnet Detail Page Parse" in result.output
    assert "Has human title" in result.output
    assert "Fontana Warehouse Project" in result.output
    assert "human_label" in result.output


def test_ceqanet_detail_parse_cli_rejects_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "detail.html"
    output_path = tmp_path / "detail.json"
    input_path.write_text(_detail_html(), encoding="utf-8")

    result = runner.invoke(
        app,
        ["parse", "--input", str(input_path), "--output", str(output_path)],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_detail_parse_cli_rejects_bad_snapshot_index(tmp_path: Path) -> None:
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
