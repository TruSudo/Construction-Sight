"""Guarded native reuse of the original CEQAnet operator export and ZIP verifier.

Only an explicitly configured, retained local chain report may be packaged.
The original export validators do all normalization and integrity verification.
No acquisition, source database mutation, lead, message or bid is created.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from constructionsight.ceqanet_operator_archive import build_ceqanet_operator_archive
from constructionsight.ceqanet_operator_archive_verify import verify_ceqanet_operator_archive
from constructionsight.ceqanet_operator_export import build_ceqanet_operator_export
from constructionsight.ceqanet_operator_package import build_ceqanet_operator_package
from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_SHA = re.compile(r"[0-9a-f]{64}")
_MAX_INPUT = 16 * 1024 * 1024


def _report(chain_report: Path | None) -> tuple[str, dict[str, Any]] | None:
    if chain_report is None:
        return None
    raw = read_runtime_artifact(chain_report, max_bytes=_MAX_INPUT)
    digest = hashlib.sha256(raw).hexdigest()
    report = json.loads(raw)
    if not isinstance(report, dict):
        raise ValueError("retained CEQAnet chain report must be an object")
    metadata = report.get("metadata")
    if (
        not isinstance(metadata, dict)
        or metadata.get("schema_version") != "ceqanet_chain_report.v1"
    ):
        raise ValueError("retained CEQAnet chain report schema is incompatible")
    return digest, report


def original_ceqanet_export_status(chain_report: Path | None) -> dict[str, Any]:
    selected = _report(chain_report)
    return {
        "schema_version": "constructionsight.original-ceqanet-export-status/v1",
        "configured": selected is not None,
        "available": selected is not None,
        "retained_report_sha256": selected[0] if selected else None,
        "network_executed": False,
        "source_database_mutated": False,
        "commercial_actions_authorized": False,
    }


def original_ceqanet_export(
    directory: Path,
    chain_report: Path | None,
    *,
    expected_report_sha256: str,
    caller_confirmation: bool,
) -> dict[str, Any]:
    if not caller_confirmation:
        raise ValueError("explicit original report export confirmation required")
    if not _SHA.fullmatch(expected_report_sha256):
        raise ValueError("invalid retained chain report digest")
    selected = _report(chain_report)
    if selected is None:
        raise ValueError("original CEQAnet report is not configured")
    digest, payload = selected
    if digest != expected_report_sha256:
        raise ValueError("chain report changed; repeat source inspection")
    exports = directory / "original-ceqanet-exports"
    if exports.is_symlink():
        raise ValueError("local operator export root cannot be a symlink")
    exports.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = exports / digest
    archive = exports / (digest + ".zip")
    if output.is_symlink() or archive.is_symlink():
        raise ValueError("operator export target cannot be a symlink")
    if archive.exists():
        receipt = verify_ceqanet_operator_archive(archive_path=archive)
        if not receipt.passed:
            raise ValueError("existing archive failed integrity verification")
        existing = read_runtime_artifact(archive, max_bytes=128 * 1024 * 1024)
        with zipfile.ZipFile(BytesIO(existing)) as verified_zip:
            original_package = json.loads(verified_zip.read("operator-package.json"))
        if original_package != build_ceqanet_operator_package(payload).to_dict():
            raise ValueError("existing verified archive belongs to a different source report")
        return {
            "schema_version": "constructionsight.original-ceqanet-export/v1",
            "retained_report_sha256": digest,
            "archive_sha256": hashlib.sha256(existing).hexdigest(),
            "archive_available": True,
            "verification_passed": True,
            "existing_verified_archive": True,
            "archive_url": "/api/source-ceqanet-export-download?sha256=" + digest,
            "network_executed": False, "source_database_mutated": False,
            "commercial_actions_authorized": False,
        }
    result = build_ceqanet_operator_export(payload, output_dir=output).to_dict()
    metadata = result["metadata"]
    if not isinstance(metadata, dict) or metadata.get("verification_passed") is not True:
        raise ValueError("original CEQAnet export bundle verification failed")
    archive_receipt = build_ceqanet_operator_archive(
        source_dir=output, archive_path=archive, require_verified=True
    ).to_dict()
    verified = verify_ceqanet_operator_archive(archive_path=archive)
    if not verified.passed:
        raise ValueError("original CEQAnet ZIP failed post-write integrity verification")
    return {
        "schema_version": "constructionsight.original-ceqanet-export/v1",
        "retained_report_sha256": digest,
        "archive_sha256": archive_receipt["metadata"]["sha256"],
        "archive_available": True,
        "verification_passed": True,
        "existing_verified_archive": False,
        "archive_url": "/api/source-ceqanet-export-download?sha256=" + digest,
        "network_executed": False,
        "source_database_mutated": False,
        "commercial_actions_authorized": False,
    }


def original_ceqanet_archive_path(
    directory: Path, *, expected_report_sha256: str,
) -> Path:
    if not _SHA.fullmatch(expected_report_sha256):
        raise ValueError("invalid original CEQAnet export identity")
    path = directory / "original-ceqanet-exports" / (expected_report_sha256 + ".zip")
    if path.is_symlink() or not path.is_file():
        raise ValueError("verified original CEQAnet archive does not exist")
    verification = verify_ceqanet_operator_archive(archive_path=path)
    if not verification.passed:
        raise ValueError("original CEQAnet archive integrity check failed")
    return path
