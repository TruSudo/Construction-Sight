from typer.testing import CliRunner

from constructionsight.cli import app


def test_audit_source_coverage_cli_passes_for_seed_registry() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["audit-source-coverage", "data/source_registry.seed.json"],
    )

    assert result.exit_code == 0
    assert "Source Adapter Coverage Audit" in result.output
    assert "Source records" in result.output
    assert "Issues" in result.output
    assert "0" in result.output
    assert "Passed" in result.output
    assert "True" in result.output
