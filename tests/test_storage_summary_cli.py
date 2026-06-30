import json

from typer.testing import CliRunner

from constructionsight.storage_summary_cli import app, build_storage_summary


def test_build_storage_summary_initializes_known_tables() -> None:
    summaries = build_storage_summary("sqlite:///:memory:")
    by_table = {summary.table_name: summary for summary in summaries}

    assert by_table["parcel_core_records"].exists is True
    assert by_table["site_resolution_results"].exists is True
    assert by_table["lead_workflows"].exists is True
    assert by_table["result_ledgers"].exists is True
    assert by_table["parcel_core_records"].row_count == 0


def test_storage_summary_cli_renders_table() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["summary", "--database-url", "sqlite:///:memory:"])

    assert result.exit_code == 0
    assert "ConstructionSight Storage Summary" in result.output
    assert "parcel_core_records" in result.output
    assert "lead_workflows" in result.output


def test_storage_summary_cli_outputs_json() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["summary", "--database-url", "sqlite:///:memory:", "--json-output"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    by_table = {item["table_name"]: item for item in payload}
    assert by_table["parcel_core_records"]["exists"] is True
    assert by_table["result_share_records"]["row_count"] == 0
