import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_operator_bundle_cli import app

runner = CliRunner()


def _operator_package(path: Path) -> None:
    payload = {
        "metadata": {
            "schema_version": "ceqanet_operator_package.v1",
            "result_record_count": 1,
            "ceqa_record_count": 1,
            "site_count": 1,
            "entity_count": 0,
            "operation_count": 1,
            "warning_count": 0,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "persistence_preview": {
            "metadata": {"schema_version": "ceqanet_persistence_preview.v1"},
            "ceqa_records": [
                {
                    "ceqa_key": "ceqa:ceqanet:2017101033",
                    "title": "Countywide Plan",
                    "state_clearinghouse_number": "2017101033",
                    "county": "San Bernardino",
                    "lead_agency": "County Agency",
                }
            ],
        },
        "write_plan": {
            "metadata": {"schema_version": "ceqanet_write_plan.v1"},
            "operations": [
                {
                    "operation_id": "ceqa_records:ceqa:ceqanet:2017101033",
                    "action": "upsert_preview",
                    "target_collection": "ceqa_records",
                    "target_key": "ceqa:ceqanet:2017101033",
                }
            ],
        },
        "warnings": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_operator_bundle_cli_renders_summary(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    bundle_dir = tmp_path / "bundle"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--output-dir",
            str(bundle_dir),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Operator Bundle" in result.output
    assert "Bundle Artifacts" in result.output
    assert (bundle_dir / "operator-report.md").exists()
    assert (bundle_dir / "manifest.json").exists()


def test_ceqanet_operator_bundle_cli_emits_json(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    bundle_dir = tmp_path / "bundle"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--output-dir",
            str(bundle_dir),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_operator_bundle.v1"
    assert payload["metadata"]["input"]["operator_package_path"] == str(package_path)
    assert payload["metadata"]["artifact_count"] == 4
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False


def test_ceqanet_operator_bundle_cli_writes_manifest_output(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    bundle_dir = tmp_path / "bundle"
    manifest_path = tmp_path / "bundle-manifest.json"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--output-dir",
            str(bundle_dir),
            "--json-output",
            "--output",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator bundle manifest JSON" in result.output
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["artifact_count"] == 4


def test_ceqanet_operator_bundle_cli_rejects_output_without_json(tmp_path: Path) -> None:
    package_path = tmp_path / "operator-package.json"
    _operator_package(package_path)

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--output",
            str(tmp_path / "manifest.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_operator_bundle_cli_rejects_bad_package(tmp_path: Path) -> None:
    package_path = tmp_path / "bad-package.json"
    package_path.write_text(
        json.dumps({"metadata": {"schema_version": "wrong.v1"}}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "build",
            "--operator-package",
            str(package_path),
            "--output-dir",
            str(tmp_path / "bundle"),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "ceqanet_operator_package.v1" in result.output
