"""One-request CEQAnet CSV execution and independent evidence verification."""

from __future__ import annotations

import base64
import binascii
import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from constructionsight.ceqanet_csv_live_models import (
    CeqanetCsvLiveExecution,
    CeqanetCsvLiveVerification,
)
from constructionsight.ceqanet_csv_models import (
    CeqanetCsvExportRequest,
    CeqanetCsvInspection,
)
from constructionsight.ceqanet_csv_service import (
    inspect_ceqanet_csv_bytes,
    parse_ceqanet_csv_export_url,
)

_USER_AGENT = "ConstructionSight-CEQAnetCSV/1.0 (+lawful-public-record-review)"
_ACCEPT = "text/csv,application/csv,application/vnd.ms-excel,text/plain;q=0.8,*/*;q=0.1"


class CeqanetCsvLiveHttpResponse(Protocol):
    """Read-only response contract used by the one-request executor."""

    @property
    def status_code(self) -> int:
        """Return the HTTP response status."""

    @property
    def content(self) -> bytes:
        """Return the exact response bytes."""

    @property
    def url(self) -> Any:
        """Return the final response URL."""

    @property
    def headers(self) -> Mapping[str, str]:
        """Return response headers through a read-only mapping contract."""


class CeqanetCsvLiveHttpClient(Protocol):
    """Minimal client contract used by the bounded live CSV executor."""

    def get(
        self,
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
    ) -> CeqanetCsvLiveHttpResponse:
        """Fetch one official public CSV URL."""


@dataclass(frozen=True)
class _HttpxCsvResponseAdapter:
    status_code: int
    content: bytes
    url: str
    headers: dict[str, str]


class _HttpxCsvClientAdapter:
    """Expose httpx.Client through the intentionally narrow executor protocol."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def get(
        self,
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
    ) -> CeqanetCsvLiveHttpResponse:
        """Fetch one URL and narrow the rich HTTPX response contract."""

        response = self._client.get(
            url,
            follow_redirects=follow_redirects,
            timeout=timeout,
        )
        return _HttpxCsvResponseAdapter(
            status_code=response.status_code,
            content=response.content,
            url=str(response.url),
            headers=dict(response.headers),
        )


def execute_ceqanet_csv_live_request(
    request: CeqanetCsvExportRequest,
    *,
    execute_live: bool,
    client: CeqanetCsvLiveHttpClient | None = None,
    timeout_seconds: float = 20.0,
    max_body_bytes: int = 10_000_000,
    max_retained_rows: int = 1_000,
) -> CeqanetCsvLiveExecution:
    """Execute exactly one explicit GET and retain a tamper-evident response envelope."""

    canonical_request = parse_ceqanet_csv_export_url(request.source_url)
    if canonical_request != request:
        raise ValueError("CEQAnet CSV request fields do not agree with source_url")
    if not execute_live:
        raise ValueError("explicit live authorization is required for CEQAnet CSV execution")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    if max_body_bytes < 1 or max_body_bytes > 10_000_000:
        raise ValueError("max_body_bytes must be between 1 and 10000000")
    if max_retained_rows < 0:
        raise ValueError("max_retained_rows cannot be negative")

    if client is not None:
        return _execute_with_client(
            request,
            client,
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
            max_retained_rows=max_retained_rows,
        )

    with httpx.Client(
        headers={"User-Agent": _USER_AGENT, "Accept": _ACCEPT},
    ) as owned_client:
        return _execute_with_client(
            request,
            _HttpxCsvClientAdapter(owned_client),
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
            max_retained_rows=max_retained_rows,
        )


def verify_ceqanet_csv_live_execution(
    execution: CeqanetCsvLiveExecution,
) -> CeqanetCsvLiveVerification:
    """Independently verify network, response, body, and offline-inspection evidence."""

    findings: list[str] = []
    try:
        execution.assert_integrity()
    except ValueError as exc:
        findings.append(str(exc))

    if execution.request_url != execution.request.source_url:
        findings.append("live CSV request_url does not match the approved request identity")
    try:
        final_request = parse_ceqanet_csv_export_url(execution.final_url)
    except ValueError as exc:
        findings.append(f"live CSV final URL is invalid: {exc}")
    else:
        if final_request != execution.request:
            findings.append("live CSV final URL does not match the approved request identity")

    method = _widen_str(execution.method)
    retry_count = _widen_int(execution.retry_count)
    network_executed = _widen_bool(execution.network_executed)
    documents_downloaded = _widen_bool(execution.documents_downloaded)
    persistence_mutated = _widen_bool(execution.persistence_mutated)
    if method != "GET":
        findings.append("live CSV execution method is not GET")
    if retry_count != 0:
        findings.append("live CSV execution reports a retry")
    if not network_executed:
        findings.append("live CSV execution does not affirm network execution")
    if documents_downloaded:
        findings.append("live CSV execution reports CEQA document downloads")
    if persistence_mutated:
        findings.append("live CSV execution reports persistence mutation")
    if execution.status_code != 200:
        findings.append(f"live CSV response status is not 200: {execution.status_code}")
    if execution.error is not None:
        findings.append(f"live CSV execution recorded error: {execution.error}")

    try:
        retained = execution.retained_body_bytes()
    except (ValueError, binascii.Error) as exc:
        findings.append(f"retained CSV body is not valid Base64: {exc.__class__.__name__}")
        retained = b""
    if len(retained) != execution.retained_body_byte_length:
        findings.append("retained CSV byte length does not match decoded bytes")
    if execution.retained_body_complete:
        if execution.retained_body_byte_length != execution.observed_body_byte_length:
            findings.append("complete retained CSV length does not match observed response length")
        if hashlib.sha256(retained).hexdigest() != execution.body_sha256:
            findings.append("retained CSV SHA-256 does not match response evidence")
    else:
        findings.append("live CSV response body was not retained completely")
        if execution.retained_body_byte_length != 0:
            findings.append("incomplete CSV response retained partial bytes")

    if (
        execution.status_code == 200
        and execution.error is None
        and execution.retained_body_complete
    ):
        try:
            recomputed_inspection = inspect_ceqanet_csv_bytes(
                execution.request,
                retained,
                content_type=execution.content_type,
                max_retained_rows=(
                    execution.inspection.retained_row_count
                    if execution.inspection is not None
                    else 1_000
                ),
            )
        except ValueError as exc:
            findings.append(f"live CSV offline inspection failed: {exc}")
        else:
            if execution.inspection is None:
                findings.append("live CSV execution lacks the successful offline inspection")
            elif recomputed_inspection != execution.inspection:
                findings.append("live CSV inspection does not match the retained response bytes")
            try:
                recomputed_inspection.assert_integrity()
            except ValueError as exc:
                findings.append(str(exc))

    if execution.inspection_error is not None:
        findings.append(f"live CSV inspection recorded error: {execution.inspection_error}")
    if execution.inspection is not None:
        try:
            execution.inspection.assert_integrity()
        except ValueError as exc:
            findings.append(str(exc))

    return CeqanetCsvLiveVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        request_url=execution.request_url,
        status_code=execution.status_code,
        inspection_digest=(
            execution.inspection.inspection_digest
            if execution.inspection is not None
            else None
        ),
        execution_digest=execution.execution_digest,
    )


def _execute_with_client(
    request: CeqanetCsvExportRequest,
    client: CeqanetCsvLiveHttpClient,
    *,
    timeout_seconds: float,
    max_body_bytes: int,
    max_retained_rows: int,
) -> CeqanetCsvLiveExecution:
    try:
        response = client.get(
            request.source_url,
            follow_redirects=True,
            timeout=timeout_seconds,
        )
    except httpx.HTTPError as exc:
        return _build_execution(
            request=request,
            final_url=request.source_url,
            status_code=None,
            content_type=None,
            content_disposition=None,
            body=b"",
            retained_complete=True,
            error=exc.__class__.__name__,
            inspection=None,
            inspection_error=None,
        )

    body = response.content
    content_type = response.headers.get("content-type")
    content_disposition = response.headers.get("content-disposition")
    retained_complete = len(body) <= max_body_bytes
    retained_body = body if retained_complete else b""
    error = None if retained_complete else "response_exceeds_max_body_bytes"
    inspection: CeqanetCsvInspection | None = None
    inspection_error = None
    if response.status_code == 200 and retained_complete:
        try:
            inspection = inspect_ceqanet_csv_bytes(
                request,
                retained_body,
                content_type=content_type,
                max_retained_rows=max_retained_rows,
            )
        except ValueError as exc:
            inspection_error = str(exc)

    return _build_execution(
        request=request,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=content_type,
        content_disposition=content_disposition,
        body=body,
        retained_complete=retained_complete,
        error=error,
        inspection=inspection,
        inspection_error=inspection_error,
    )


def _build_execution(
    *,
    request: CeqanetCsvExportRequest,
    final_url: str,
    status_code: int | None,
    content_type: str | None,
    content_disposition: str | None,
    body: bytes,
    retained_complete: bool,
    error: str | None,
    inspection: CeqanetCsvInspection | None,
    inspection_error: str | None,
) -> CeqanetCsvLiveExecution:
    retained = body if retained_complete else b""
    payload: dict[str, Any] = {
        "request": request,
        "request_url": request.source_url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "content_disposition": content_disposition,
        "observed_body_byte_length": len(body),
        "retained_body_base64": base64.b64encode(retained).decode("ascii"),
        "retained_body_byte_length": len(retained),
        "retained_body_complete": retained_complete,
        "body_sha256": hashlib.sha256(body).hexdigest(),
        "error": error,
        "inspection": inspection,
        "inspection_error": inspection_error,
    }
    draft = CeqanetCsvLiveExecution(
        **payload,
        execution_digest="0" * 64,
    )
    return draft.model_copy(update={"execution_digest": draft.computed_digest()})


def _widen_bool(value: bool) -> bool:
    return value


def _widen_int(value: int) -> int:
    return value


def _widen_str(value: str) -> str:
    return value
