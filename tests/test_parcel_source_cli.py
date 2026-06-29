import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.parcel_source_cli import app

runner = CliRunner()


def test_parcel_source_cli_renders_matrix() -> None:
    result = runner.invoke(app, ["matrix", "--county", "San Bernardino"])

    assert result.exit_code == 0
    assert "Parcel Source Registry" in result.output
    assert "San Bernardino" in result.output


def test_parcel_source_cli_emits_filtered_json() -> None:
    result = runner.invoke(
        app,
        [
            "matrix",
            "--provider-kind",
            "county_gis",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload
    assert {row["provider_kind"] for row in payload} == {"county_gis"}


def test_parcel_source_cli_writes_report_json(tmp_path: Path) -> None:
    output_path = tmp_path / "parcel-source-report.json"

    result = runner.invoke(app, ["report", "--json-output", "--output", str(output_path)])

    assert result.exit_code == 0
    assert "Wrote parcel source registry report JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["sources_reviewed"] >= 4
    assert payload["target_sources"]


def test_parcel_source_cli_rejects_output_without_json(tmp_path: Path) -> None:
    result = runner.invoke(app, ["matrix", "--output", str(tmp_path / "matrix.json")])

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
