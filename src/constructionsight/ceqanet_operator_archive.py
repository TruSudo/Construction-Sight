"""CEQAnet operator archive service.

This module creates a deterministic ZIP archive from an existing verified CEQAnet
operator export directory. It performs no network requests, database access, or
persistence mutation.
"""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

from constructionsight.ceqanet_operator_bundle_verify import verify_ceqanet_operator_bundle

_ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
_MAX_ARCHIVE_MEMBER_BYTES = 16 * 1024 * 1024
_MAX_ARCHIVE_TOTAL_BYTES = 64 * 1024 * 1024
_MAX_ARCHIVE_FILE_BYTES = 128 * 1024 * 1024
_ARCHIVE_CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class CeqanetOperatorArchive:
    """Result from creating one deterministic operator archive."""

    archive_path: Path
    source_dir: Path
    archived_files: tuple[str, ...]
    byte_count: int
    sha256: str
    verification: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe archive payload."""

        verification_metadata = _metadata_object(self.verification, field_name="verification")
        return {
            "metadata": {
                "schema_version": "ceqanet_operator_archive.v1",
                "archive_path": str(self.archive_path),
                "source_dir": str(self.source_dir),
                "file_count": len(self.archived_files),
                "byte_count": self.byte_count,
                "sha256": self.sha256,
                "verification_schema_version": verification_metadata.get("schema_version"),
                "verification_passed": verification_metadata.get("passed"),
                "network_executed": False,
                "database_opened": False,
                "persistence_mutated": False,
            },
            "archived_files": list(self.archived_files),
            "verification": self.verification,
        }


def build_ceqanet_operator_archive(
    *,
    source_dir: Path,
    archive_path: Path,
    require_verified: bool = True,
) -> CeqanetOperatorArchive:
    """Create a deterministic ZIP archive from a CEQAnet operator export directory."""

    verification = verify_ceqanet_operator_bundle(bundle_dir=source_dir).to_dict()
    verification_metadata = _metadata_object(verification, field_name="verification")
    verification_passed = verification_metadata.get("passed") is True
    if require_verified and not verification_passed:
        raise ValueError(
            "Refusing archive creation because operator bundle verification did not pass."
        )

    archived_files = _manifest_filenames(verification)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    _write_zip(source_dir=source_dir, archive_path=archive_path, filenames=archived_files)
    archive_digest = hashlib.sha256()
    archive_byte_count = 0
    with archive_path.open("rb") as archive_file:
        while True:
            chunk = archive_file.read(
                min(
                    _ARCHIVE_CHUNK_BYTES,
                    _MAX_ARCHIVE_FILE_BYTES - archive_byte_count + 1,
                )
            )
            if not chunk:
                break
            archive_byte_count += len(chunk)
            if archive_byte_count > _MAX_ARCHIVE_FILE_BYTES:
                raise ValueError("CEQAnet ZIP output exceeds the archive byte limit")
            archive_digest.update(chunk)

    return CeqanetOperatorArchive(
        archive_path=archive_path,
        source_dir=source_dir,
        archived_files=tuple(archived_files),
        byte_count=archive_byte_count,
        sha256=archive_digest.hexdigest(),
        verification=verification,
    )


def _manifest_filenames(verification: dict[str, object]) -> list[str]:
    """Return sorted manifest filenames from verification output."""

    artifacts = verification.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("Bundle verification must contain artifacts list.")

    filenames: list[str] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        filename = artifact.get("filename")
        status = artifact.get("status")
        if isinstance(filename, str) and filename and status == "verified":
            filenames.append(filename)

    if "manifest.json" not in filenames:
        filenames.append("manifest.json")
    return sorted(set(filenames))


def _write_zip(*, source_dir: Path, archive_path: Path, filenames: list[str]) -> None:
    """Write deterministic ZIP archive."""

    if len(filenames) > 128:
        raise ValueError("CEQAnet ZIP output exceeds the entry limit")
    remaining_bytes = _MAX_ARCHIVE_TOTAL_BYTES
    with zipfile.ZipFile(archive_path, mode="w") as archive:
        for filename in filenames:
            if (
                filename in {".", ".."}
                or filename != Path(filename).name
                or "\\" in filename
                or "\x00" in filename
            ):
                raise ValueError("CEQAnet ZIP source must be a safe basename")
            source_path = source_dir / filename
            if not source_path.is_file():
                raise ValueError(f"Archive source file missing: {source_path}")
            info = zipfile.ZipInfo(filename=filename, date_time=_ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            written = 0
            with source_path.open("rb") as source_file:
                with archive.open(info, mode="w") as archive_entry:
                    while True:
                        chunk = source_file.read(
                            min(
                                _ARCHIVE_CHUNK_BYTES,
                                _MAX_ARCHIVE_MEMBER_BYTES - written + 1,
                                remaining_bytes + 1,
                            )
                        )
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > _MAX_ARCHIVE_MEMBER_BYTES:
                            raise ValueError("CEQAnet archive member exceeds the byte limit")
                        remaining_bytes -= len(chunk)
                        if remaining_bytes < 0:
                            raise ValueError("CEQAnet ZIP output exceeds the total byte limit")
                        archive_entry.write(chunk)


def _metadata_object(payload: dict[str, object], *, field_name: str) -> dict[str, object]:
    """Return metadata object from a payload."""

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError(f"{field_name} must contain metadata.")
    return metadata
