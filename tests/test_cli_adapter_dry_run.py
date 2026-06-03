from typer.testing import CliRunner

from constructionsight.cli import app


def test_dry_run_adapters_cli_runs_against_seed_registry() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["dry-run-adapters", "data/source_registry.seed.json", "--limit", "2"],
    )

    assert result.exit_code == 0
    assert "Adapter Dry Run" in result.output
    assert "Dry-ran 2 adapter sources." in result.output
    assert "success" in result.output


def test_dry_run_adapters_cli_respects_zero_record_placeholder_behavior() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["dry-run-adapters", "data/source_registry.seed.json", "--limit", "1"],
    )

    assert result.exit_code == 0
    assert "Records" in result.output
    assert "0" in result.output
