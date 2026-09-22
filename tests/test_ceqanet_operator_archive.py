import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import constructionsight.ceqanet_operator_archive as archive_writer
from constructionsight.ceqanet_operator_archive import build_ceqanet_operator_archive


@pytest.mark.parametrize("attack", ("ancestor", "final", "swap"))
def test_archive_publication_never_writes_through_replaced_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, attack: str,
) -> None:
    source = tmp_path / "source"
    _write_export_dir(source)
    outside = tmp_path / "outside"
    outside.mkdir()
    retained = outside / "retained.zip"
    retained.write_bytes(b"prior archive")
    output_dir = tmp_path / "output"
    if attack == "ancestor":
        output_dir.symlink_to(outside, target_is_directory=True)
    else:
        output_dir.mkdir()
    archive_path = output_dir / "archive.zip"
    if attack == "final":
        archive_path.symlink_to(retained)
    if attack == "swap":
        write_zip = archive_writer._write_zip

        def swap_then_write(**kwargs):
            output_dir.rename(tmp_path / "parked")
            output_dir.symlink_to(outside, target_is_directory=True)
            write_zip(**kwargs)

        monkeypatch.setattr(archive_writer, "_write_zip", swap_then_write)
    with pytest.raises((OSError, ValueError)):
        build_ceqanet_operator_archive(source_dir=source, archive_path=archive_path)
    assert retained.read_bytes() == b"prior archive"
    assert list(outside.iterdir()) == [retained]


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


def test_build_ceqanet_operator_archive_creates_deterministic_zip(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)

    archive = build_ceqanet_operator_archive(
        source_dir=export_dir,
        archive_path=archive_path,
    ).to_dict()

    assert archive["metadata"]["schema_version"] == "ceqanet_operator_archive.v1"
    assert archive["metadata"]["file_count"] == 6
    assert archive["metadata"]["byte_count"] == archive_path.stat().st_size
    assert archive["metadata"]["sha256"] == hashlib.sha256(
        archive_path.read_bytes()
    ).hexdigest()
    assert archive["metadata"]["verification_passed"] is True
    assert archive["metadata"]["network_executed"] is False
    assert archive["metadata"]["database_opened"] is False
    assert archive["metadata"]["persistence_mutated"] is False

    with zipfile.ZipFile(archive_path) as archive_file:
        assert archive_file.namelist() == sorted(
            [
                "manifest.json",
                "operator-package.json",
                "operator-report.json",
                "operator-report.md",
                "persistence-preview.json",
                "write-plan.json",
            ]
        )
        assert archive_file.read("operator-report.md") == b"# CEQAnet Operator Report\n"

    second_archive_path = tmp_path / "operator-export-second.zip"
    second_archive = build_ceqanet_operator_archive(
        source_dir=export_dir,
        archive_path=second_archive_path,
    ).to_dict()
    assert second_archive["metadata"]["sha256"] == archive["metadata"]["sha256"]


def test_build_ceqanet_operator_archive_rejects_unverified_bundle(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    _write_export_dir(export_dir)
    (export_dir / "operator-report.md").write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="verification did not pass"):
        build_ceqanet_operator_archive(
            source_dir=export_dir,
            archive_path=tmp_path / "operator-export.zip",
        )


def test_build_ceqanet_operator_archive_can_allow_unverified_bundle(tmp_path: Path) -> None:
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "operator-export.zip"
    _write_export_dir(export_dir)
    (export_dir / "operator-report.md").write_text("changed\n", encoding="utf-8")

    archive = build_ceqanet_operator_archive(
        source_dir=export_dir,
        archive_path=archive_path,
        require_verified=False,
    ).to_dict()

    assert archive["metadata"]["verification_passed"] is False
    assert archive_path.exists()


def test_archive_writer_streams_source_and_output_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "bundle"
    _write_export_dir(source_dir)
    archive_path = tmp_path / "bounded.zip"

    def forbid_read_bytes(_self: Path) -> bytes:
        raise AssertionError("archive writer must not materialize whole source/output files")

    monkeypatch.setattr(Path, "read_bytes", forbid_read_bytes)
    result = build_ceqanet_operator_archive(
        source_dir=source_dir, archive_path=archive_path
    )
    assert result.byte_count == archive_path.stat().st_size
    assert result.sha256


def test_archive_writer_rejects_source_growth_during_archive_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "bundle"
    _write_export_dir(source_dir)
    archive_path = tmp_path / "oversized.zip"
    real_write_zip = archive_writer._write_zip

    def grow_source_and_write(
        *,
        source_dir: Path,
        archive_path: Path,
        filenames: list[str],
        expected_content: dict[str, tuple[int, str]],
    ) -> None:
        with (source_dir / "operator-report.md").open("wb") as grown:
            grown.truncate(16 * 1024 * 1024 + 1)
        real_write_zip(
            source_dir=source_dir,
            archive_path=archive_path,
            filenames=filenames,
            expected_content=expected_content,
        )

    monkeypatch.setattr(archive_writer, "_write_zip", grow_source_and_write)
    with pytest.raises(ValueError, match="member exceeds the byte limit"):
        build_ceqanet_operator_archive(
            source_dir=source_dir, archive_path=archive_path
        )


def test_archive_writer_rejects_same_length_mutation_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "bundle"
    _write_export_dir(source_dir)
    archive_path = tmp_path / "existing.zip"
    archive_path.write_bytes(b"existing archive must survive failed rewrite")
    real_write_zip = archive_writer._write_zip

    def mutate_source_and_write(
        *,
        source_dir: Path,
        archive_path: Path,
        filenames: list[str],
        expected_content: dict[str, tuple[int, str]],
    ) -> None:
        report = source_dir / "operator-report.md"
        report.write_bytes(b"x" * report.stat().st_size)
        real_write_zip(
            source_dir=source_dir,
            archive_path=archive_path,
            filenames=filenames,
            expected_content=expected_content,
        )

    monkeypatch.setattr(archive_writer, "_write_zip", mutate_source_and_write)
    with pytest.raises(ValueError, match="changed since verification"):
        build_ceqanet_operator_archive(
            source_dir=source_dir,
            archive_path=archive_path,
        )
    assert archive_path.read_bytes() == b"existing archive must survive failed rewrite"
    assert list(tmp_path.glob(".ceqanet-archive-*.tmp")) == []


def test_archive_writer_rejects_manifest_mutation_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "bundle"
    _write_export_dir(source_dir)
    archive_path = tmp_path / "operator-export.zip"
    real_write_zip = archive_writer._write_zip

    def mutate_manifest_and_write(
        *,
        source_dir: Path,
        archive_path: Path,
        filenames: list[str],
        expected_content: dict[str, tuple[int, str]],
    ) -> None:
        manifest = source_dir / "manifest.json"
        manifest.write_bytes(manifest.read_bytes() + b" ")
        real_write_zip(
            source_dir=source_dir,
            archive_path=archive_path,
            filenames=filenames,
            expected_content=expected_content,
        )

    monkeypatch.setattr(archive_writer, "_write_zip", mutate_manifest_and_write)
    with pytest.raises(ValueError, match="changed since verification"):
        build_ceqanet_operator_archive(
            source_dir=source_dir,
            archive_path=archive_path,
        )
    assert not archive_path.exists()


def test_archive_writer_rejects_symlink_swap_after_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_dir = tmp_path / "bundle"
    _write_export_dir(source_dir)
    archive_path = tmp_path / "operator-export.zip"
    outside = tmp_path / "outside.txt"
    outside.write_bytes((source_dir / "operator-report.md").read_bytes())
    real_write_zip = archive_writer._write_zip

    def swap_source_and_write(
        *,
        source_dir: Path,
        archive_path: Path,
        filenames: list[str],
        expected_content: dict[str, tuple[int, str]],
    ) -> None:
        source = source_dir / "operator-report.md"
        source.unlink()
        source.symlink_to(outside)
        real_write_zip(
            source_dir=source_dir,
            archive_path=archive_path,
            filenames=filenames,
            expected_content=expected_content,
        )

    monkeypatch.setattr(archive_writer, "_write_zip", swap_source_and_write)
    with pytest.raises(ValueError, match="not a symlink"):
        build_ceqanet_operator_archive(
            source_dir=source_dir,
            archive_path=archive_path,
        )
    assert not archive_path.exists()


@pytest.mark.parametrize("require_verified", [True, False])
def test_archive_rejects_manifest_inventory_swap_during_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, require_verified: bool,
) -> None:
    """ZIP must not pair one verified inventory with another manifest snapshot."""

    source_dir = tmp_path / "bundle"
    _write_export_dir(source_dir)
    manifest_path = source_dir / "manifest.json"
    original_manifest = manifest_path.read_bytes()
    alternate_manifest = json.loads(original_manifest)
    alternate_manifest["artifacts"] = alternate_manifest["artifacts"][:-1]
    alternate_manifest["metadata"]["artifact_count"] = 4
    alternate_bytes = json.dumps(alternate_manifest).encode("utf-8")
    old_archive = b"previous committed ZIP bytes"
    archive_path = tmp_path / "operator-export.zip"
    archive_path.write_bytes(old_archive)
    actual_verify = archive_writer.verify_ceqanet_operator_bundle

    def verify_swapped_manifest(*, bundle_dir: Path):
        manifest_path.write_bytes(alternate_bytes)
        try:
            result = actual_verify(bundle_dir=bundle_dir)
            assert result.passed
            assert len(result.artifacts) == 4
            return result
        finally:
            manifest_path.write_bytes(original_manifest)

    monkeypatch.setattr(
        archive_writer, "verify_ceqanet_operator_bundle", verify_swapped_manifest,
    )
    with pytest.raises(ValueError, match="changed since verification"):
        build_ceqanet_operator_archive(
            source_dir=source_dir,
            archive_path=archive_path,
            require_verified=require_verified,
        )
    assert archive_path.read_bytes() == old_archive
    assert manifest_path.read_bytes() == original_manifest
