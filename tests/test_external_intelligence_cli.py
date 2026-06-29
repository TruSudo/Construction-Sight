import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.external_intelligence_cli import app

runner = CliRunner()


def test_external_capability_cli_renders_matrix() -> None:
    result = runner.invoke(app, ["matrix", "--platform", "shovels"])

    assert result.exit_code == 0
    assert "External Intelligence Capability Matrix" in result.output
    assert "shovels" in result.output


def test_external_capability_cli_emits_filtered_json() -> None:
    result = runner.invoke(
        app,
        [
            "matrix",
            "--platform",
            "regrid",
            "--domain",
            "parcel_geometry",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload
    assert {row["platform"] for row in payload} == {"regrid"}
    assert {row["domain"] for row in payload} == {"parcel_geometry"}


def test_external_capability_cli_writes_gap_report_json(tmp_path: Path) -> None:
    output_path = tmp_path / "gap-report.json"

    result = runner.invoke(
        app,
        ["gap-report", "--json-output", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert "Wrote external capability gap report JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["capabilities_reviewed"] >= 10
    assert payload["outperform_targets"]
    assert payload["blocked_by_license"]


def test_external_capability_cli_rejects_output_without_json(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["matrix", "--output", str(tmp_path / "matrix.json")],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
