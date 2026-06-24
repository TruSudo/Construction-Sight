import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_operator_bundle_verify_cli import app

runner = CliRunner()


def _write_bundle_manifest(bundle_dir: Path) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "operator-report.md").write_text("# CEQAnet Operator Report\n", encoding="utf-8")
    data = (bundle_dir / "operator-report.md").read_bytes()
    payload = {
        "metadata": {
            "schema_version": "ceqanet_operator_bundle.v1",
            "artifact_count": 1,
            "network_executed": False,
            "database_opened": False,
            "persistence_mutated": False,
        },
        "artifacts": [
            {
                "filename": "operator-report.md",
                "artifact_type": "operator_report_markdown",
                "byte_count": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ],
    }
    (bundle_dir / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")


def test_ceqanet_operator_bundle_verify_cli_renders_summary(tmp_path: Path) -> None:
    _write_bundle_manifest(tmp_path)

    result = runner.invoke(
        app,
        [
            "verify",
            "--bundle-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Operator Bundle Verification" in result.output
    assert "Artifact Verification" in result.output
    assert "operator-report.md" in result.output


def test_ceqanet_operator_bundle_verify_cli_emits_json(tmp_path: Path) -> None:
    _write_bundle_manifest(tmp_path)

    result = runner.invoke(
        app,
        [
            "verify",
            "--bundle-dir",
            str(tmp_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_operator_bundle_verification.v1"
    assert payload["metadata"]["verified_count"] == 1
    assert payload["metadata"]["passed"] is True
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False


def test_ceqanet_operator_bundle_verify_cli_writes_json_output(tmp_path: Path) -> None:
    output_path = tmp_path / "verification.json"
    bundle_dir = tmp_path / "bundle"
    _write_bundle_manifest(bundle_dir)

    result = runner.invoke(
        app,
        [
            "verify",
            "--bundle-dir",
            str(bundle_dir),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator bundle verification JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["verified_count"] == 1


def test_ceqanet_operator_bundle_verify_cli_rejects_output_without_json(tmp_path: Path) -> None:
    _write_bundle_manifest(tmp_path)

    result = runner.invoke(
        app,
        [
            "verify",
            "--bundle-dir",
            str(tmp_path),
            "--output",
            str(tmp_path / "verification.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_operator_bundle_verify_cli_rejects_bad_manifest(tmp_path: Path) -> None:
    (tmp_path / "manifest.json").write_text(
        json.dumps({"metadata": {"schema_version": "wrong.v1"}, "artifacts": []}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "verify",
            "--bundle-dir",
            str(tmp_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "ceqanet_operator_bundle.v1" in result.output
