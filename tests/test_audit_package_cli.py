from typer.testing import CliRunner

from constructionsight.audit_package_cli import app


def test_audit_package_cli_outputs_json(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(
        """
        [
          {
            "jurisdiction": {
              "name": "Test City",
              "county": "San Bernardino",
              "state": "CA",
              "jurisdiction_type": "city"
            },
            "source_name": "Test Source",
            "source_type": "city_portal",
            "platform_family": "accela_aca",
            "public_url": "https://example.invalid/source",
            "verification_status": "unverified"
          }
        ]
        """,
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["build", str(registry_path), "--json-output"])

    assert result.exit_code == 0
    assert '"source_count": 1' in result.output
    assert '"keep_seed_only": 1' in result.output
