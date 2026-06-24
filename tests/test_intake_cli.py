import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.intake_cli import app

runner = CliRunner()


def test_intake_cli_renders_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "record.txt"
    input_path.write_text(
        "City of Hesperia APN: 123-456-78 at 123 Main Street",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "inspect",
            "--input",
            str(input_path),
            "--source-name",
            "manual note",
        ],
    )

    assert result.exit_code == 0
    assert "Universal Intake Inspection" in result.output
    assert "Extracted Material Facts" in result.output


def test_intake_cli_emits_json(tmp_path: Path) -> None:
    input_path = tmp_path / "record.json"
    input_path.write_text(
        '{"apn": "123-456-78", "address": "123 Main Street"}',
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "inspect",
            "--input",
            str(input_path),
            "--source-name",
            "json record",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["format_detection"]["format_family"] == "json"
    assert payload["routing"] == "opportunity_intake"
    assert payload["evidence"]["source_name"] == "json record"


def test_intake_cli_writes_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "record.html"
    output_path = tmp_path / "intake.json"
    input_path.write_text("<html><body>APN: 123-456-78</body></html>", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "inspect",
            "--input",
            str(input_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote universal intake JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["format_detection"]["format_family"] == "html"


def test_intake_cli_rejects_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "record.txt"
    input_path.write_text("APN: 123-456-78", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "inspect",
            "--input",
            str(input_path),
            "--output",
            str(tmp_path / "intake.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
