import hashlib
import json
import zipfile
from pathlib import Path

from constructionsight.ceqanet_operator_archive import build_ceqanet_operator_archive
from constructionsight.ceqanet_operator_archive_verify import verify_ceqanet_operator_archive

_ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
_ARCHIVE_EXTERNAL_ATTR = 0o100644 << 16


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


def test_verify_ceqanet_operator_archive_accepts_deterministic_verified_archive(
    tmp_path: Path,
) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    build_ceqanet_operator_archive(source_dir=export_dir, archive_path=archive_path)

    verification = verify_ceqanet_operator_archive(archive_path=archive_path).to_dict()

    assert verification["metadata"]["schema_version"] == (
        "ceqanet_operator_archive_verification.v1"
    )
    assert verification["metadata"]["zip_entry_count"] == 6
    assert verification["metadata"]["archived_file_count"] == 6
    assert verification["metadata"]["artifact_count"] == 5
    assert verification["metadata"]["verified_count"] == 5
    assert verification["metadata"]["missing_count"] == 0
    assert verification["metadata"]["mismatch_count"] == 0
    assert verification["metadata"]["manifest_status"] == "verified"
    assert verification["metadata"]["passed"] is True
    assert verification["metadata"]["network_executed"] is False
    assert verification["metadata"]["database_opened"] is False
    assert verification["metadata"]["persistence_mutated"] is False


def test_verify_ceqanet_operator_archive_detects_artifact_mismatch(
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

    verification = verify_ceqanet_operator_archive(archive_path=archive_path).to_dict()

    assert verification["metadata"]["passed"] is False
    assert verification["metadata"]["mismatch_count"] == 1
    mismatches = [
        artifact for artifact in verification["artifacts"] if artifact["status"] == "mismatch"
    ]
    assert mismatches == [
        {
            "filename": "operator-report.md",
            "artifact_type": "operator_report_md",
            "expected_sha256": hashlib.sha256(b"# CEQAnet Operator Report\n").hexdigest(),
            "actual_sha256": hashlib.sha256(b"changed\n").hexdigest(),
            "expected_byte_count": len(b"# CEQAnet Operator Report\n"),
            "actual_byte_count": len(b"changed\n"),
            "status": "mismatch",
            "reason": "sha256 or byte_count mismatch",
        }
    ]


def test_verify_ceqanet_operator_archive_detects_missing_manifest(tmp_path: Path) -> None:
    archive_path = tmp_path / "operator-export.zip"
    with zipfile.ZipFile(archive_path, mode="w") as archive_file:
        _write_archive_entry(
            archive_file,
            filename="operator-report.md",
            data=b"# CEQAnet Operator Report\n",
        )

    verification = verify_ceqanet_operator_archive(archive_path=archive_path).to_dict()

    assert verification["metadata"]["passed"] is False
    assert verification["metadata"]["manifest_status"] == "missing"
    assert verification["metadata"]["artifact_count"] == 0
    assert verification["metadata"]["archive_issue_count"] == 1
    assert verification["archive_issues"] == [
        {"filename": "manifest.json", "reason": "manifest missing"}
    ]


def test_verify_ceqanet_operator_archive_detects_nondeterministic_zip_metadata(
    tmp_path: Path,
) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    with zipfile.ZipFile(archive_path, mode="w") as archive_file:
        archive_file.writestr("manifest.json", (export_dir / "manifest.json").read_bytes())

    verification = verify_ceqanet_operator_archive(archive_path=archive_path).to_dict()

    assert verification["metadata"]["passed"] is False
    assert verification["metadata"]["archive_issue_count"] == 1
    assert verification["archive_issues"] == [
        {"filename": "manifest.json", "reason": "timestamp must be (2026, 1, 1, 0, 0, 0)"}
    ]
