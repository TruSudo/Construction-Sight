import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.intake_service import IntakeInspectionInput, inspect_lawful_input
from constructionsight.opportunity_cli import app

runner = CliRunner()


def _write_intake_json(path: Path, content: bytes) -> None:
    record = inspect_lawful_input(
        IntakeInspectionInput(content=content, source_name="manual transition note")
    )
    path.write_text(json.dumps(record.to_dict()), encoding="utf-8")


def test_opportunity_cli_renders_summary(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    _write_intake_json(input_path, b"APN: 123-456-78. Permit No. BLD20260001 issued.")

    result = runner.invoke(app, ["evaluate", "--input", str(input_path)])

    assert result.exit_code == 0
    assert "Opportunity Candidate" in result.output
    assert "Transition Events" in result.output


def test_opportunity_cli_emits_json(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    _write_intake_json(input_path, b"SCH No. 2026061234 for warehouse construction.")

    result = runner.invoke(app, ["evaluate", "--input", str(input_path), "--json-output"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["readiness"] in {"monitor", "research_ready", "outreach_ready"}
    assert payload["transition_events"]


def test_opportunity_cli_writes_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    output_path = tmp_path / "candidate.json"
    _write_intake_json(input_path, b"Permit No. BLD20260001 issued. Value: $1,000,000.")

    result = runner.invoke(
        app,
        [
            "evaluate",
            "--input",
            str(input_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote opportunity candidate JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["lead_score"] > 0


def test_opportunity_cli_rejects_output_without_json(tmp_path: Path) -> None:
    input_path = tmp_path / "intake.json"
    _write_intake_json(input_path, b"APN: 123-456-78")

    result = runner.invoke(
        app,
        ["evaluate", "--input", str(input_path), "--output", str(tmp_path / "candidate.json")],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output
