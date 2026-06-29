import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.intake_service import IntakeInspectionInput, inspect_lawful_input
from constructionsight.site_resolution_cli import app

runner = CliRunner()


def _write_intake_json(path: Path, content: bytes) -> None:
    record = inspect_lawful_input(
        IntakeInspectionInput(content=content, source_name="site test source")
    )
    path.write_text(json.dumps(record.to_dict()), encoding="utf-8")


def test_site_resolution_cli_renders_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    _write_intake_json(input_path, b"APN: 123-456-78. Project site: 123 Main St.")

    result = runner.invoke(app, ["resolve-intake", "--input", str(input_path)])

    assert result.exit_code == 0
    assert "Site Resolution" in result.output
    assert "Site Candidates" in result.output


def test_site_resolution_cli_emits_json(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    _write_intake_json(input_path, b"APN: 123-456-78. Project site: 123 Main St.")

    result = runner.invoke(
        app,
        ["resolve-intake", "--input", str(input_path), "--json-output"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] in {"partial", "resolved"}
    assert payload["candidates"]


def test_site_resolution_cli_writes_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    output_path = tmp_path / "site-resolution.json"
    _write_intake_json(input_path, b"APN: 123-456-78. Project site: 123 Main St.")

    result = runner.invoke(
        app,
        [
            "resolve-intake",
            "--input",
            str(input_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote site-resolution JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["primary_site_key"].startswith("site:")


def test_site_resolution_cli_rejects_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    _write_intake_json(input_path, b"APN: 123-456-78")

    result = runner.invoke(
        app,
        [
            "resolve-intake",
            "--input",
            str(input_path),
            "--output",
            str(tmp_path / "site-resolution.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
