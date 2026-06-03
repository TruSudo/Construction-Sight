from typer.testing import CliRunner

from constructionsight.cli import app


def test_audit_adapters_cli_passes_for_default_contracts() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["audit-adapters"])

    assert result.exit_code == 0
    assert "Adapter Contract Audit" in result.output
    assert "Missing specs" in result.output
    assert "none" in result.output
    assert "Passed" in result.output
    assert "True" in result.output
