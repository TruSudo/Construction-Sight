import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from constructionsight.ceqanet_fixture_query_cli import app

runner = CliRunner()


def _fixture_rows() -> list[dict[str, Any]]:
    return [
        {
            "sch_number": "2026000001",
            "title": "North Fontana Logistics Center",
            "county": "San Bernardino",
            "lead_agency": "City of Fontana",
            "document_type": "EIR",
            "received_date": "2026-01-10",
            "posted_date": "2026-01-12",
            "description": "Warehouse logistics project near Sierra Avenue.",
            "project_location": "Fontana, CA",
            "record_url": "https://ceqanet.lci.ca.gov/2026000001",
        },
        {
            "sch_number": "2026000002",
            "title": "Riverside Residential Infill",
            "county": "Riverside",
            "lead_agency": "City of Riverside",
            "document_type": "Notice of Exemption",
            "received_date": "2026-02-05",
            "posted_date": "2026-02-08",
            "description": "Residential infill project.",
            "project_location": "Riverside, CA",
            "record_url": "https://ceqanet.lci.ca.gov/2026000002",
        },
    ]


def _write_fixture(path: Path) -> None:
    path.write_text(json.dumps(_fixture_rows()), encoding="utf-8")


def test_ceqanet_fixture_query_cli_renders_table(tmp_path: Path) -> None:
    fixture_path = tmp_path / "ceqanet_rows.json"
    _write_fixture(fixture_path)

    result = runner.invoke(
        app,
        [
            "query",
            str(fixture_path),
            "--county",
            "San Bernardino",
            "--high-signal-only",
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Fixture Query" in result.output
    assert "Source records" in result.output
    assert "Matched records" in result.output
    assert "North Fontana Logistics Center" in result.output
    assert "Riverside Residential Infill" not in result.output


def test_ceqanet_fixture_query_cli_emits_json(tmp_path: Path) -> None:
    fixture_path = tmp_path / "ceqanet_rows.json"
    _write_fixture(fixture_path)

    result = runner.invoke(
        app,
        [
            "query",
            str(fixture_path),
            "--text",
            "warehouse",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_fixture_query.v1"
    assert payload["metadata"]["source_record_count"] == 2
    assert payload["metadata"]["matched_record_count"] == 1
    assert payload["records"][0]["title"] == "North Fontana Logistics Center"


def test_ceqanet_fixture_query_cli_writes_json_output(tmp_path: Path) -> None:
    fixture_path = tmp_path / "ceqanet_rows.json"
    output_path = tmp_path / "query-output.json"
    _write_fixture(fixture_path)

    result = runner.invoke(
        app,
        [
            "query",
            str(fixture_path),
            "--document-type",
            "Notice of Exemption",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet fixture query JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["matched_record_count"] == 1
    assert payload["records"][0]["title"] == "Riverside Residential Infill"


def test_ceqanet_fixture_query_cli_rejects_output_without_json(tmp_path: Path) -> None:
    fixture_path = tmp_path / "ceqanet_rows.json"
    output_path = tmp_path / "query-output.json"
    _write_fixture(fixture_path)

    result = runner.invoke(app, ["query", str(fixture_path), "--output", str(output_path)])

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_fixture_query_cli_rejects_non_array_fixture(tmp_path: Path) -> None:
    fixture_path = tmp_path / "bad.json"
    fixture_path.write_text(json.dumps({"not": "an array"}), encoding="utf-8")

    result = runner.invoke(app, ["query", str(fixture_path)])

    assert result.exit_code != 0
    assert "CEQAnet fixture JSON must be an array" in result.output
