from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_listing_execute_cli import app

runner = CliRunner()


def test_ceqanet_listing_execute_cli_requires_explicit_live_consent() -> None:
    result = runner.invoke(app, ["execute", "--county", "San Bernardino"])

    assert result.exit_code != 0
    assert "Refusing live execution without --execute-live" in result.output


def test_ceqanet_listing_execute_cli_blocks_captcha_access() -> None:
    result = runner.invoke(
        app,
        [
            "execute",
            "--county",
            "San Bernardino",
            "--has-captcha",
            "--execute-live",
            "--json-output",
        ],
    )

    assert result.exit_code == 1
    assert "lawful access preflight denied execution" in result.output
    assert "captcha" in result.output.lower()


def test_ceqanet_listing_execute_cli_does_not_write_blocked_output(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "execution.json"
    result = runner.invoke(
        app,
        [
            "execute",
            "--county",
            "Riverside",
            "--robots-disallows-collection",
            "--execute-live",
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 1
    assert "robots" in result.output.lower()
    assert not output_path.exists()


def test_ceqanet_listing_execute_cli_rejects_output_without_json(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "execution.json"
    result = runner.invoke(
        app,
        [
            "execute",
            "--county",
            "San Bernardino",
            "--execute-live",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_listing_execute_cli_rejects_unbounded_query_even_with_live_consent() -> None:
    result = runner.invoke(app, ["execute", "--execute-live"])

    assert result.exit_code != 0
    assert "requires at least one bounding query filter" in result.output


def test_ceqanet_listing_execute_cli_requires_access_fact_basis() -> None:
    result = runner.invoke(
        app,
        [
            "execute",
            "--county",
            "San Bernardino",
            "--execute-live",
            "--json-output",
        ],
    )

    assert result.exit_code == 1
    assert "lawful access preflight denied execution" in result.output
    assert "fact basis" in result.output
