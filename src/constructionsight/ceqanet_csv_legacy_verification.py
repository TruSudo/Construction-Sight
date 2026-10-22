"""Read-only verification of the archived CEQAnet CSV execution.v1 envelope.

This is deliberately NOT the old executor. The historical model's digest and
CSV semantics are reproduced only to inspect already-retained evidence.
Historical integrity does not grant current source access, identity, import,
outreach, or any commercial authority.
"""

from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import parse_qsl, urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator

from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
    inspect_ceqanet_csv_bytes,
)

_MAX_ARCHIVED_BODY = 10_000_000


class _ArchivedRequest(BaseModel):
    """Exact original v1 request fields; no live execution authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ceqanet_csv_export_request.v1"] = (
        "ceqanet_csv_export_request.v1"
    )
    scope: Literal["project", "document"]
    sch_number: str = Field(pattern=r"^\d{10}$")
    document_id: int | None = Field(default=None, ge=1)
    method: Literal["GET"] = "GET"
    documents_downloaded: Literal[False] = False
    persistence_authorized: Literal[False] = False

    @model_validator(mode="after")
    def require_scope_identity(self) -> _ArchivedRequest:
        if self.scope == "project" and self.document_id is not None:
            raise ValueError("historical project request cannot contain document_id")
        if self.scope == "document" and self.document_id is None:
            raise ValueError("historical document request requires document_id")
        return self


class _ArchivedExecution(BaseModel):
    """Retained v1 execution shape, not a current authorization decision."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["ceqanet_csv_export_execution.v1"] = (
        "ceqanet_csv_export_execution.v1"
    )
    request: _ArchivedRequest
    request_url: str = Field(min_length=1)
    final_url: str = Field(min_length=1)
    status_code: int | None = Field(default=None, ge=100, le=599)
    content_type: str | None = None
    content_disposition: str | None = None
    body_base64: str
    body_byte_length: int = Field(ge=0)
    body_sha256: str = Field(min_length=64, max_length=64)
    network_executed: bool
    documents_downloaded: Literal[False] = False
    persistence_mutated: Literal[False] = False
    error: str | None = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    execution_digest: str = Field(min_length=64, max_length=64)

    def calculated_digest(self) -> str:
        """Exact old JSON canonicalization, excluding timestamp and own digest."""
        payload = self.model_dump(
            mode="json", exclude={"executed_at", "execution_digest"},
        )
        rendered = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=True, default=str,
        ).encode("utf-8")
        return hashlib.sha256(rendered).hexdigest()


def _verified_official_url(url: str, canonical: str) -> bool:
    """Preserve old ordered query identity, with stricter origin safeguards."""
    try:
        given = urlsplit(url)
        expected = urlsplit(canonical)
        request_port = given.port
    except ValueError:
        return False
    return (
        given.scheme == "https"
        and given.hostname == expected.hostname
        and given.path == expected.path
        and given.username is None
        and given.password is None
        and request_port in (None, 443)
        and not given.fragment
        and parse_qsl(given.query, keep_blank_values=True)
        == parse_qsl(expected.query, keep_blank_values=True)
    )


def _archived_csv_rows(body: bytes) -> tuple[int, list[str]]:
    """Original DictReader semantics, including an empty header-only report."""
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ValueError("historical CSV lacks a header")
    headers = [header.strip() for header in reader.fieldnames]
    if any(not header for header in headers):
        raise ValueError("historical CSV headers must be nonblank")
    if len(headers) != len(set(headers)):
        raise ValueError("historical CSV headers must be unique")
    count = 0
    for row in reader:
        if None in row:
            raise ValueError("historical CSV row has extra columns")
        count += 1
    return count, headers


def verify_archived_ceqanet_csv_execution(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Check a retained v1 artifact offline, without granting current authority.

    'passed' means internally consistent under historical CSV v1 semantics;
    it is not authentication of the collector, current source access, or
    admissibility for persistence. The current guarded parser has a separately
    reported result and cannot silently promote a legacy artifact.
    """
    execution = _ArchivedExecution.model_validate(payload)
    request = execution.request
    current_request = build_ceqanet_csv_export_request(
        sch_number=request.sch_number,
        document_id=request.document_id,
    )
    canonical = current_request.source_url
    findings: list[str] = []
    if execution.execution_digest != execution.calculated_digest():
        findings.append("historical execution canonical digest mismatch")
    if execution.request_url != canonical:
        findings.append("historical request URL differs from official canonical request")
    for label, url in (("request", execution.request_url), ("final", execution.final_url)):
        if not _verified_official_url(url, canonical):
            findings.append(f"historical {label} URL fails official origin/query review")
    if not execution.network_executed:
        findings.append("historical artifact does not claim an executed request")
    if execution.status_code != 200:
        findings.append(f"historical HTTP response is not successful: {execution.status_code}")
    if execution.error is not None:
        findings.append("historical artifact recorded an execution error")

    body = b""
    # Keep the old maximum accepted envelope bounded even if its JSON is forged.
    if len(execution.body_base64) > 4 * ((_MAX_ARCHIVED_BODY + 2) // 3):
        findings.append("historical response exceeds archival body limit")
    else:
        try:
            body = base64.b64decode(execution.body_base64, validate=True)
        except (ValueError, binascii.Error):
            findings.append("historical body_base64 is invalid")
    if len(body) > _MAX_ARCHIVED_BODY:
        findings.append("historical decoded response exceeds archival body limit")
    if len(body) != execution.body_byte_length:
        findings.append("historical body byte length mismatch")
    if hashlib.sha256(body).hexdigest() != execution.body_sha256:
        findings.append("historical body SHA-256 mismatch")

    archived_rows: int | None = None
    archived_headers: list[str] = []
    if execution.status_code == 200 and execution.error is None:
        try:
            archived_rows, archived_headers = _archived_csv_rows(body)
        except (UnicodeDecodeError, ValueError, csv.Error) as exc:
            findings.append(f"historical CSV parse failed: {exc}")

    archive_passed = not findings
    current_parser_compatible = False
    current_parser_findings: list[str] = []
    if archive_passed:
        try:
            inspection = inspect_ceqanet_csv_bytes(
                current_request, body,
                content_type=execution.content_type,
            )
            inspection.assert_integrity()
            current_parser_compatible = True
        except ValueError as exc:
            current_parser_findings.append(str(exc))

    return {
        "schema_version": "constructionsight.ceqanet_csv_legacy_offline_verification.v1",
        "passed": archive_passed,
        "finding_count": len(findings),
        "findings": findings,
        "archive_schema": execution.schema_version,
        "archive_execution_digest": execution.execution_digest,
        "archive_body_sha256": execution.body_sha256,
        "historical_claimed_network_executed": execution.network_executed,
        "historical_parsed_row_count": archived_rows,
        "historical_parsed_headers": archived_headers,
        "current_parser_compatible": current_parser_compatible,
        "current_parser_findings": current_parser_findings,
        "network_executed_by_verification": False,
        "persistence_mutated": False,
        "current_source_authorized": False,
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
        "limitations": [
            "An internally consistent historical record does not authenticate its collector.",
            "Historical execution evidence does not establish current source access rights.",
            "This read-only operation cannot import, promote, or authorize commerce.",
        ],
    }
