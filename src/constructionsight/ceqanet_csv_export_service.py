"""Governed official CEQAnet CSV planning, execution, parsing, and verification."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx

from constructionsight.ceqanet_csv_export_models import (
    CeqanetCsvExportExecution,
    CeqanetCsvExportRequest,
    CeqanetCsvExportVerification,
    CeqanetCsvParseReport,
    CeqanetCsvRecord,
    CeqanetCsvScope,
)

_CSV_ENDPOINT = "https://ceqanet.lci.ca.gov/Search"
_CSV_HOST = "ceqanet.lci.ca.gov"
_USER_AGENT = "ConstructionSight-CEQAnetCSV/1.0 (+lawful-public-record-review)"


class CeqanetCsvHttpResponse(Protocol):
    """Minimal HTTP response contract needed by the CSV executor."""

    status_code: int
    content: bytes
    url: Any
    headers: Mapping[str, str]


class CeqanetCsvHttpClient(Protocol):
    """Minimal bounded GET client used by the CSV executor."""

    def get(
        self,
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
    ) -> CeqanetCsvHttpResponse:
        """Fetch one public CSV URL."""


def build_ceqanet_csv_export_url(request: CeqanetCsvExportRequest) -> str:
    """Build the exact official source-provided CSV URL."""

    if request.scope is CeqanetCsvScope.PROJECT:
        params = (("OutputFormat", "CSV"), ("Sch", request.sch_number))
    else:
        if request.document_id is None:
            raise ValueError("document CSV request lacks document_id")
        params = (
            ("DocumentId", str(request.document_id)),
            ("OutputFormat", "CSV"),
            ("Sch", request.sch_number),
        )
    return f"{_CSV_ENDPOINT}?{urlencode(params)}"


def parse_ceqanet_csv_bytes(
    body: bytes,
    *,
    source_url: str,
) -> CeqanetCsvParseReport:
    """Strictly parse retained official CSV bytes without network access."""

    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        raise ValueError("CEQAnet CSV response lacks a header row")

    headers = [header.strip() for header in reader.fieldnames]
    if any(not header for header in headers):
        raise ValueError("CEQAnet CSV headers must be nonblank")
    if len(headers) != len(set(headers)):
        raise ValueError("CEQAnet CSV headers must be unique")

    records: list[CeqanetCsvRecord] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValueError(f"CEQAnet CSV row {row_number} has more values than headers")
        values = {
            header: "" if row.get(original_header) is None else str(row[original_header])
            for original_header, header in zip(reader.fieldnames, headers, strict=True)
        }
        records.append(CeqanetCsvRecord(row_number=row_number, values=values))

    return CeqanetCsvParseReport(
        source_url=source_url,
        body_byte_length=len(body),
        body_sha256=hashlib.sha256(body).hexdigest(),
        headers=headers,
        row_count=len(records),
        records=records,
        limitations=[
            "CSV values are preserved as source text without semantic field inference",
            "this parse does not authorize persistence or attachment downloads",
        ],
    )


def execute_ceqanet_csv_export(
    request: CeqanetCsvExportRequest,
    *,
    execute_live: bool,
    client: CeqanetCsvHttpClient | None = None,
    timeout_seconds: float = 20.0,
    max_body_bytes: int = 2_000_000,
) -> CeqanetCsvExportExecution:
    """Execute one explicitly authorized, bounded, GET-only official CSV request."""

    if not execute_live:
        raise ValueError("explicit live authorization is required for CEQAnet CSV execution")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if max_body_bytes < 1:
        raise ValueError("max_body_bytes must be at least one")

    request_url = build_ceqanet_csv_export_url(request)
    http_client = client or httpx.Client(
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.1",
        }
    )

    try:
        response = http_client.get(
            request_url,
            follow_redirects=True,
            timeout=timeout_seconds,
        )
    except httpx.HTTPError as exc:
        return _build_execution(
            request=request,
            request_url=request_url,
            final_url=request_url,
            status_code=None,
            content_type=None,
            content_disposition=None,
            body=b"",
            network_executed=True,
            error=exc.__class__.__name__,
        )

    body = response.content
    if len(body) > max_body_bytes:
        raise ValueError(
            f"CEQAnet CSV response exceeds max_body_bytes: {len(body)} > {max_body_bytes}"
        )
    return _build_execution(
        request=request,
        request_url=request_url,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        content_disposition=response.headers.get("content-disposition"),
        body=body,
        network_executed=True,
        error=None,
    )


def verify_ceqanet_csv_execution(
    execution: CeqanetCsvExportExecution,
) -> CeqanetCsvExportVerification:
    """Verify execution integrity, request authority, response boundary, and CSV shape."""

    findings: list[str] = []
    try:
        execution.assert_integrity()
    except ValueError as exc:
        findings.append(str(exc))

    expected_url = build_ceqanet_csv_export_url(execution.request)
    if execution.request_url != expected_url:
        findings.append("CSV request_url does not match the deterministic request")
    _verify_url(execution.request_url, execution.request, findings, label="request")
    _verify_url(execution.final_url, execution.request, findings, label="final")

    if not execution.network_executed:
        findings.append("CSV execution does not affirm network execution")
    if execution.documents_downloaded:
        findings.append("CSV execution reports document downloads")
    if execution.persistence_mutated:
        findings.append("CSV execution reports persistence mutation")
    if execution.status_code != 200:
        findings.append(f"CSV response status is not 200: {execution.status_code}")
    if execution.error is not None:
        findings.append(f"CSV execution recorded error: {execution.error}")

    parsed: CeqanetCsvParseReport | None = None
    try:
        body = execution.body_bytes()
    except (ValueError, TypeError) as exc:
        findings.append(f"CSV body_base64 is invalid: {exc.__class__.__name__}")
        body = b""
    if len(body) != execution.body_byte_length:
        findings.append("CSV body byte length does not match retained bytes")
    if hashlib.sha256(body).hexdigest() != execution.body_sha256:
        findings.append("CSV body SHA-256 does not match retained bytes")

    if execution.status_code == 200 and execution.error is None:
        try:
            parsed = parse_ceqanet_csv_bytes(body, source_url=execution.final_url)
        except (UnicodeDecodeError, ValueError, csv.Error) as exc:
            findings.append(f"CSV parse failed: {exc}")

    return CeqanetCsvExportVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        parsed_row_count=parsed.row_count if parsed is not None else None,
        parsed_headers=parsed.headers if parsed is not None else [],
        request_url=execution.request_url,
        execution_digest=execution.execution_digest,
    )


def _build_execution(
    *,
    request: CeqanetCsvExportRequest,
    request_url: str,
    final_url: str,
    status_code: int | None,
    content_type: str | None,
    content_disposition: str | None,
    body: bytes,
    network_executed: bool,
    error: str | None,
) -> CeqanetCsvExportExecution:
    draft = CeqanetCsvExportExecution(
        request=request,
        request_url=request_url,
        final_url=final_url,
        status_code=status_code,
        content_type=content_type,
        content_disposition=content_disposition,
        body_base64=base64.b64encode(body).decode("ascii"),
        body_byte_length=len(body),
        body_sha256=hashlib.sha256(body).hexdigest(),
        network_executed=network_executed,
        error=error,
        execution_digest="0" * 64,
    )
    return draft.model_copy(update={"execution_digest": draft.computed_digest()})


def _verify_url(
    url: str,
    request: CeqanetCsvExportRequest,
    findings: list[str],
    *,
    label: str,
) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != _CSV_HOST:
        findings.append(f"CSV {label} URL is outside the approved official HTTPS host")
    if parsed.path != "/Search":
        findings.append(f"CSV {label} URL path is not /Search")

    actual_query = parse_qsl(parsed.query, keep_blank_values=True)
    expected_query = parse_qsl(
        urlparse(build_ceqanet_csv_export_url(request)).query,
        keep_blank_values=True,
    )
    if actual_query != expected_query:
        findings.append(f"CSV {label} URL query does not match the request contract")
