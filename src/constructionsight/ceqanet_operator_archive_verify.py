"""CEQAnet operator archive verification service.

This module verifies deterministic CEQAnet operator ZIP archives without extracting
files to disk. It performs no network requests, database access, or persistence
mutation.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

_ARCHIVE_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
_ARCHIVE_EXTERNAL_ATTR = 0o100644 << 16
_MAX_ZIP_ARCHIVE_BYTES = 128 * 1024 * 1024
_MAX_ZIP_ENTRIES = 128
_MAX_ZIP_ENTRY_BYTES = 16 * 1024 * 1024
_MAX_ZIP_MANIFEST_BYTES = 1024 * 1024
_MAX_ZIP_TOTAL_BYTES = 64 * 1024 * 1024
_ZIP_READ_CHUNK_BYTES = 64 * 1024

ArchiveArtifactStatus = Literal["verified", "missing", "mismatch"]
ManifestStatus = Literal["verified", "missing", "malformed"]


@dataclass(frozen=True)
class CeqanetArchiveArtifactVerification:
    """Verification result for one manifest-listed archive artifact."""

    filename: str
    artifact_type: str
    expected_sha256: str
    actual_sha256: str | None
    expected_byte_count: int | None
    actual_byte_count: int | None
    status: ArchiveArtifactStatus
    reason: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe artifact verification payload."""

        return {
            "filename": self.filename,
            "artifact_type": self.artifact_type,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "expected_byte_count": self.expected_byte_count,
            "actual_byte_count": self.actual_byte_count,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CeqanetOperatorArchiveVerification:
    """Verification result for one deterministic CEQAnet operator archive."""

    archive_path: Path
    zip_entry_count: int
    archived_files: tuple[str, ...]
    manifest_status: ManifestStatus
    artifacts: tuple[CeqanetArchiveArtifactVerification, ...]
    malformed_artifacts: tuple[dict[str, object], ...]
    archive_issues: tuple[dict[str, object], ...]
    duplicate_filenames: tuple[str, ...]

    @property
    def verified_count(self) -> int:
        """Return verified artifact count."""

        return sum(1 for artifact in self.artifacts if artifact.status == "verified")

    @property
    def missing_count(self) -> int:
        """Return missing artifact count."""

        return sum(1 for artifact in self.artifacts if artifact.status == "missing")

    @property
    def mismatch_count(self) -> int:
        """Return mismatched artifact count."""

        return sum(1 for artifact in self.artifacts if artifact.status == "mismatch")

    @property
    def passed(self) -> bool:
        """Return whether the archive passed all deterministic verification checks."""

        return (
            self.manifest_status == "verified"
            and self.missing_count == 0
            and self.mismatch_count == 0
            and not self.malformed_artifacts
            and not self.archive_issues
            and not self.duplicate_filenames
        )

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe archive verification payload."""

        return {
            "metadata": {
                "schema_version": "ceqanet_operator_archive_verification.v1",
                "archive_path": str(self.archive_path),
                "zip_entry_count": self.zip_entry_count,
                "archived_file_count": len(self.archived_files),
                "artifact_count": len(self.artifacts),
                "verified_count": self.verified_count,
                "missing_count": self.missing_count,
                "mismatch_count": self.mismatch_count,
                "malformed_artifact_count": len(self.malformed_artifacts),
                "archive_issue_count": len(self.archive_issues),
                "duplicate_filename_count": len(self.duplicate_filenames),
                "manifest_status": self.manifest_status,
                "passed": self.passed,
                "network_executed": False,
                "database_opened": False,
                "persistence_mutated": False,
            },
            "archived_files": list(self.archived_files),
            "duplicate_filenames": list(self.duplicate_filenames),
            "archive_issues": list(self.archive_issues),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "malformed_artifacts": list(self.malformed_artifacts),
        }


def verify_ceqanet_operator_archive(
    *,
    archive_path: Path,
) -> CeqanetOperatorArchiveVerification:
    """Verify a deterministic CEQAnet operator ZIP archive."""

    if not archive_path.is_file():
        raise ValueError(f"CEQAnet operator archive not found: {archive_path}")
    if archive_path.stat().st_size > _MAX_ZIP_ARCHIVE_BYTES:
        raise ValueError("CEQAnet operator archive exceeds the ZIP byte limit")

    try:
        with zipfile.ZipFile(archive_path) as archive_file:
            infos = archive_file.infolist()
            _require_bounded_archive_metadata(infos)
            remaining_bytes = [_MAX_ZIP_TOTAL_BYTES]
            filenames = [info.filename for info in infos]
            duplicate_filenames = _duplicate_filenames(filenames)
            archive_issues = _archive_entry_issues(infos)
            manifest_status, manifest, manifest_issues = _load_manifest_from_archive(
                archive_file, remaining_bytes=remaining_bytes
            )
            archive_issues.extend(manifest_issues)

            artifacts: list[CeqanetArchiveArtifactVerification] = []
            malformed_artifacts: list[dict[str, object]] = []
            if manifest is not None:
                for index, entry in enumerate(_artifact_entries(manifest)):
                    if not isinstance(entry, dict):
                        malformed_artifacts.append(
                            {"index": index, "reason": "artifact is not an object"}
                        )
                        continue
                    artifact = _verify_artifact_entry(
                        archive_file,
                        entry=cast(dict[str, Any], entry),
                        remaining_bytes=remaining_bytes,
                    )
                    if artifact is None:
                        malformed_artifacts.append(
                            {
                                "index": index,
                                "reason": "artifact missing filename, artifact_type, or sha256",
                            }
                        )
                        continue
                    artifacts.append(artifact)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"CEQAnet operator archive is not a valid ZIP: {archive_path}") from exc

    return CeqanetOperatorArchiveVerification(
        archive_path=archive_path,
        zip_entry_count=len(filenames),
        archived_files=tuple(sorted(set(filenames))),
        manifest_status=manifest_status,
        artifacts=tuple(artifacts),
        malformed_artifacts=tuple(malformed_artifacts),
        archive_issues=tuple(archive_issues),
        duplicate_filenames=duplicate_filenames,
    )


def _require_bounded_archive_metadata(infos: list[zipfile.ZipInfo]) -> None:
    """Reject excessive archive metadata before any member decompression."""

    if len(infos) > _MAX_ZIP_ENTRIES:
        raise ValueError("CEQAnet operator archive exceeds the ZIP entry limit")
    total_size = 0
    for info in infos:
        if info.file_size < 0 or info.file_size > _MAX_ZIP_ENTRY_BYTES:
            raise ValueError("CEQAnet ZIP member exceeds the entry byte limit")
        total_size += info.file_size
        if total_size > _MAX_ZIP_TOTAL_BYTES:
            raise ValueError("CEQAnet operator archive exceeds the total ZIP byte limit")


def _bounded_member_chunks(
    archive_file: zipfile.ZipFile,
    *,
    filename: str,
    member_byte_limit: int,
    remaining_bytes: list[int],
) -> Iterator[bytes]:
    """Stream a ZIP member with actual decompressed and aggregate byte ceilings."""

    actual_bytes = 0
    with archive_file.open(filename) as entry_file:
        while True:
            chunk = entry_file.read(
                min(
                    _ZIP_READ_CHUNK_BYTES,
                    member_byte_limit - actual_bytes + 1,
                    remaining_bytes[0] + 1,
                )
            )
            if not chunk:
                break
            actual_bytes += len(chunk)
            if actual_bytes > member_byte_limit:
                raise ValueError("CEQAnet ZIP member exceeds the decompressed byte limit")
            remaining_bytes[0] -= len(chunk)
            if remaining_bytes[0] < 0:
                raise ValueError("CEQAnet ZIP exceeds the total decompressed byte limit")
            yield chunk


def _duplicate_filenames(filenames: list[str]) -> tuple[str, ...]:
    """Return duplicate archive filenames."""

    counts = Counter(filenames)
    return tuple(sorted(filename for filename, count in counts.items() if count > 1))


def _archive_entry_issues(infos: list[zipfile.ZipInfo]) -> list[dict[str, object]]:
    """Return deterministic ZIP-entry metadata issues."""

    issues: list[dict[str, object]] = []
    for info in infos:
        reason = _archive_entry_issue_reason(info)
        if reason is not None:
            issues.append({"filename": info.filename, "reason": reason})
    return issues


def _archive_entry_issue_reason(info: zipfile.ZipInfo) -> str | None:
    """Return the first deterministic ZIP-entry issue, if any."""

    if info.is_dir():
        return "directory entries are not allowed"
    if not _is_safe_relative_posix_path(info.filename):
        return "filename must be a safe relative POSIX path"
    if info.date_time != _ARCHIVE_TIMESTAMP:
        return f"timestamp must be {_ARCHIVE_TIMESTAMP}"
    if info.compress_type != zipfile.ZIP_DEFLATED:
        return "compression type must be ZIP_DEFLATED"
    if info.external_attr != _ARCHIVE_EXTERNAL_ATTR:
        return f"external_attr must be {_ARCHIVE_EXTERNAL_ATTR}"
    return None


def _is_safe_relative_posix_path(filename: str) -> bool:
    """Return whether a ZIP filename is a safe relative POSIX path."""

    if not filename or "\\" in filename:
        return False
    path = PurePosixPath(filename)
    return not path.is_absolute() and ".." not in path.parts


def _load_manifest_from_archive(
    archive_file: zipfile.ZipFile,
    *,
    remaining_bytes: list[int],
) -> tuple[ManifestStatus, dict[str, Any] | None, list[dict[str, object]]]:
    """Load and validate manifest JSON from an archive."""

    if "manifest.json" not in archive_file.namelist():
        return "missing", None, [{"filename": "manifest.json", "reason": "manifest missing"}]

    try:
        raw_manifest = b"".join(
            _bounded_member_chunks(
                archive_file,
                filename="manifest.json",
                member_byte_limit=_MAX_ZIP_MANIFEST_BYTES,
                remaining_bytes=remaining_bytes,
            )
        )
        payload = json.loads(raw_manifest.decode("utf-8"))
    except UnicodeDecodeError:
        return "malformed", None, [{"filename": "manifest.json", "reason": "not UTF-8"}]
    except json.JSONDecodeError:
        return "malformed", None, [{"filename": "manifest.json", "reason": "not valid JSON"}]

    if not isinstance(payload, dict):
        return "malformed", None, [{"filename": "manifest.json", "reason": "not a JSON object"}]
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        return "malformed", None, [{"filename": "manifest.json", "reason": "metadata missing"}]
    if metadata.get("schema_version") != "ceqanet_operator_bundle.v1":
        return (
            "malformed",
            None,
            [{"filename": "manifest.json", "reason": "unsupported schema_version"}],
        )
    if not isinstance(payload.get("artifacts"), list):
        return "malformed", None, [{"filename": "manifest.json", "reason": "artifacts missing"}]
    return "verified", cast(dict[str, Any], payload), []


def _artifact_entries(manifest: dict[str, Any]) -> list[object]:
    """Return manifest artifact entries."""

    artifacts = manifest["artifacts"]
    return cast(list[object], artifacts)


def _verify_artifact_entry(
    archive_file: zipfile.ZipFile,
    *,
    entry: dict[str, Any],
    remaining_bytes: list[int],
) -> CeqanetArchiveArtifactVerification | None:
    """Verify one manifest-listed artifact against ZIP contents."""

    filename = _string_or_none(entry.get("filename"))
    artifact_type = _string_or_none(entry.get("artifact_type"))
    expected_sha256 = _string_or_none(entry.get("sha256"))
    expected_byte_count = _int_or_none(entry.get("byte_count"))
    if filename is None or artifact_type is None or expected_sha256 is None:
        return None

    actual_digest = hashlib.sha256()
    actual_byte_count = 0
    try:
        for chunk in _bounded_member_chunks(
            archive_file,
            filename=filename,
            member_byte_limit=_MAX_ZIP_ENTRY_BYTES,
            remaining_bytes=remaining_bytes,
        ):
            actual_digest.update(chunk)
            actual_byte_count += len(chunk)
    except KeyError:
        return CeqanetArchiveArtifactVerification(
            filename=filename,
            artifact_type=artifact_type,
            expected_sha256=expected_sha256,
            actual_sha256=None,
            expected_byte_count=expected_byte_count,
            actual_byte_count=None,
            status="missing",
            reason="not present in archive",
        )

    actual_sha256 = actual_digest.hexdigest()
    if actual_sha256 == expected_sha256 and (
        expected_byte_count is None or actual_byte_count == expected_byte_count
    ):
        return CeqanetArchiveArtifactVerification(
            filename=filename,
            artifact_type=artifact_type,
            expected_sha256=expected_sha256,
            actual_sha256=actual_sha256,
            expected_byte_count=expected_byte_count,
            actual_byte_count=actual_byte_count,
            status="verified",
        )

    return CeqanetArchiveArtifactVerification(
        filename=filename,
        artifact_type=artifact_type,
        expected_sha256=expected_sha256,
        actual_sha256=actual_sha256,
        expected_byte_count=expected_byte_count,
        actual_byte_count=actual_byte_count,
        status="mismatch",
        reason="sha256 or byte_count mismatch",
    )


def _string_or_none(value: object) -> str | None:
    """Return non-empty string value or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _int_or_none(value: object) -> int | None:
    """Return integer values while rejecting bools."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
