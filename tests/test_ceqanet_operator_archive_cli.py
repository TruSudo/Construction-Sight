import hashlib
import json
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_operator_archive_cli import app

runner = CliRunner()


def _write_export_dir(export_dir: Path) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "operator-package.json": "{\"package\": true}\n",
        "persistence-preview.json": "{\"preview\": true}\n",
        "write-plan.json": "{\"plan\": true}\n",
        "operator-report.json": "{\"report\": true}\n",
        "operator-report.md": "# CEQAnet Operator Report\n",
    }
    artifacts = []
    for filename, text in files.items():
        path = export_dir / filename
        path.write_text(text, encoding="utf-8")
        data = path.read_bytes()
        artifacts.append(
            {
                "filename": filename,
                "artifact_type": filename.replace(".", "_").replace("-", "_"),
                "byte_count": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    manifest = {
        "metadata": {"schema_version": "ceqanet_operator_bundle.v1", "artifact_count": 5},
        "artifacts": artifacts,
    }
    (export_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_ceqanet_operator_archive_cli_renders_summary(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)

    result = runner.invoke(
        app,
        [
            "build",
            "--source-dir",
            str(export_dir),
            "--archive",
            str(archive_path),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Operator Archive" in result.output
    assert archive_path.exists()


def test_ceqanet_operator_archive_cli_emits_json(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)

    result = runner.invoke(
        app,
        [
            "build",
            "--source-dir",
            str(export_dir),
            "--archive",
            str(archive_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == "ceqanet_operator_archive.v1"
    assert payload["metadata"]["file_count"] == 6
    assert payload["metadata"]["verification_passed"] is True
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False


def test_ceqanet_operator_archive_cli_writes_json_output(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    output_path = tmp_path / "archive.json"
    _write_export_dir(export_dir)

    result = runner.invoke(
        app,
        [
            "build",
            "--source-dir",
            str(export_dir),
            "--archive",
            str(archive_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator archive JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["file_count"] == 6


def test_ceqanet_operator_archive_cli_rejects_output_without_json(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)

    result = runner.invoke(
        app,
        [
            "build",
            "--source-dir",
            str(export_dir),
            "--archive",
            str(archive_path),
            "--output",
            str(tmp_path / "archive.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_operator_archive_cli_rejects_unverified_bundle(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    (export_dir / "operator-report.md").write_text("changed\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "build",
            "--source-dir",
            str(export_dir),
            "--archive",
            str(archive_path),
            "--json-output",
        ],
    )

    assert result.exit_code != 0
    assert "verification did not pass" in result.output
    assert not archive_path.exists()
