import hashlib
import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

from constructionsight.ceqanet_operator_archive import build_ceqanet_operator_archive
from constructionsight.ceqanet_operator_archive_verify_cli import app

_ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
_ARCHIVE_EXTERNAL_ATTR = 0o100644 << 16

runner = CliRunner()


def _write_export_dir(export_dir: Path) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "operator-package.json": '{"package": true}\n',
        "persistence-preview.json": '{"preview": true}\n',
        "write-plan.json": '{"plan": true}\n',
        "operator-report.json": '{"report": true}\n',
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
        "metadata": {
            "schema_version": "ceqanet_operator_bundle.v1",
            "artifact_count": 5,
        },
        "artifacts": artifacts,
    }
    (export_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _write_archive_entry(
    archive_file: zipfile.ZipFile,
    *,
    filename: str,
    data: bytes,
) -> None:
    info = zipfile.ZipInfo(filename=filename, date_time=_ARCHIVE_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = _ARCHIVE_EXTERNAL_ATTR
    archive_file.writestr(info, data)


def _write_archive_from_export_dir(
    export_dir: Path,
    archive_path: Path,
    *,
    overrides: dict[str, bytes] | None = None,
) -> None:
    filenames = sorted(
        [
            "manifest.json",
            "operator-package.json",
            "operator-report.json",
            "operator-report.md",
            "persistence-preview.json",
            "write-plan.json",
        ]
    )
    replacement_data = overrides or {}
    with zipfile.ZipFile(archive_path, mode="w") as archive_file:
        for filename in filenames:
            data = replacement_data.get(filename, (export_dir / filename).read_bytes())
            _write_archive_entry(archive_file, filename=filename, data=data)


def test_ceqanet_operator_archive_verify_cli_renders_summary(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    build_ceqanet_operator_archive(source_dir=export_dir, archive_path=archive_path)

    result = runner.invoke(
        app,
        [
            "verify",
            "--archive",
            str(archive_path),
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Operator Archive Verification" in result.output
    assert "passed" in result.output


def test_ceqanet_operator_archive_verify_cli_emits_json(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    build_ceqanet_operator_archive(source_dir=export_dir, archive_path=archive_path)

    result = runner.invoke(
        app,
        [
            "verify",
            "--archive",
            str(archive_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["schema_version"] == ("ceqanet_operator_archive_verification.v1")
    assert payload["metadata"]["verified_count"] == 5
    assert payload["metadata"]["passed"] is True
    assert payload["metadata"]["network_executed"] is False
    assert payload["metadata"]["database_opened"] is False
    assert payload["metadata"]["persistence_mutated"] is False


def test_ceqanet_operator_archive_verify_cli_writes_json_output(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    output_path = tmp_path / "archive-verification.json"
    _write_export_dir(export_dir)
    build_ceqanet_operator_archive(source_dir=export_dir, archive_path=archive_path)

    result = runner.invoke(
        app,
        [
            "verify",
            "--archive",
            str(archive_path),
            "--json-output",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote CEQAnet operator archive verification JSON" in result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["metadata"]["passed"] is True


def test_ceqanet_operator_archive_verify_cli_rejects_output_without_json(
    tmp_path: Path,
) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    build_ceqanet_operator_archive(source_dir=export_dir, archive_path=archive_path)

    result = runner.invoke(
        app,
        [
            "verify",
            "--archive",
            str(archive_path),
            "--output",
            str(tmp_path / "archive-verification.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--output requires --json-output" in result.output


def test_ceqanet_operator_archive_verify_cli_reports_failed_verification(
    tmp_path: Path,
) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    _write_archive_from_export_dir(
        export_dir,
        archive_path,
        overrides={"operator-report.md": b"changed\n"},
    )

    result = runner.invoke(
        app,
        [
            "verify",
            "--archive",
            str(archive_path),
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["metadata"]["passed"] is False
    assert payload["metadata"]["mismatch_count"] == 1
