import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.external_gap_cli import app

runner = CliRunner()


def test_external_gap_cli_renders_gap_matrix() -> None:
    result = runner.invoke(app, ["gaps", "--platform", "regrid"])

    assert result.exit_code == 0
    assert "Shovels/Regrid Knowledge Gaps" in result.output
    assert "regrid" in result.output


def test_external_gap_cli_emits_filtered_json() -> None:
    result = runner.invoke(
        app,
        ["gaps", "--priority", "critical", "--json-output"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload
    assert {row["priority"] for row in payload} == {"critical"}


def test_external_gap_cli_writes_roadmap_json(tmp_path: Path) -> None:
    output_path = tmp_path / "roadmap.json"

    result = runner.invoke(
        app,
        ["roadmap", "--json-output", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert "Wrote Shovels/Regrid roadmap JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload[0]["sequence"] == "1"
    assert payload[0]["step_key"] == "parcel-source-schema-preview"


def test_external_gap_cli_writes_report_json(tmp_path: Path) -> None:
    output_path = tmp_path / "report.json"

    result = runner.invoke(
        app,
        ["report", "--json-output", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert "Wrote Shovels/Regrid alignment report JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["critical_gaps"]
    assert payload["next_steps"]


def test_external_gap_cli_rejects_output_without_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["gaps", "--output", str(tmp_path / "gaps.json")],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
