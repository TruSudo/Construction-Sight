"""One-request CEQAnet CSV execution and independent evidence verification."""

from __future__ import annotations

import base64
import binascii
import hashlib
from datetime import UTC, datetime
from typing import Any

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
from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
    canonicalize_http_url,
)

_USER_AGENT = "ConstructionSight-CEQAnetCSV/1.0 (+lawful-public-record-review)"
_ACCEPTED_MEDIA_TYPES = (
    "application/csv",
    "application/vnd.ms-excel",
    "text/csv",
    "text/plain",
)


def _policy(
    *,
    request_url: str,
    timeout_seconds: float,
    max_body_bytes: int,
) -> BoundedHttpPolicy:
    return BoundedHttpPolicy(
        policy_id="CS-NET-003",
        allowed_methods=("GET",),
        allowed_hosts=("ceqanet.lci.ca.gov",),
        allowed_path_prefixes=("/Search",),
        connect_timeout_seconds=min(5.0, timeout_seconds),
        read_timeout_seconds=timeout_seconds,
        write_timeout_seconds=min(5.0, timeout_seconds),
        pool_timeout_seconds=min(5.0, timeout_seconds),
        max_response_bytes=max_body_bytes,
        accepted_media_types=_ACCEPTED_MEDIA_TYPES,
        accepted_encodings=("utf-8", "windows-1252"),
        user_agent=_USER_AGENT,
        allowed_request_urls=(request_url,),
    )


def execute_ceqanet_csv_live_request(
    request: CeqanetCsvExportRequest,
    *,
    execute_live: bool,
    timeout_seconds: float = 20.0,
    max_body_bytes: int = 10_000_000,
    max_retained_rows: int = 1_000,
    executed_at: datetime | None = None,
) -> CeqanetCsvLiveExecution:
    """Execute exactly one policy-bound GET and retain a tamper-evident envelope."""

    canonical_request = parse_ceqanet_csv_export_url(request.source_url)
    if canonical_request != request:
        raise ValueError("CEQAnet CSV request fields do not agree with source_url")
    request_url = canonicalize_http_url(request.source_url)
    if not execute_live:
        raise ValueError("explicit live authorization is required for CEQAnet CSV execution")
    if timeout_seconds <= 0 or timeout_seconds > 20.0:
        raise ValueError("timeout_seconds must be between 0 and 20")
    if max_body_bytes < 1 or max_body_bytes > 10_000_000:
        raise ValueError("max_body_bytes must be between 1 and 10000000")
    if max_retained_rows < 0 or max_retained_rows > 1_000:
        raise ValueError("max_retained_rows must be between 0 and 1000")

    observation = execute_bounded_http(
        request_url,
        "GET",
        _policy(
            request_url=request_url,
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
        ),
    )
    return _execution_from_observation(
        request,
        observation,
        max_retained_rows=max_retained_rows,
        executed_at=executed_at,
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

    runtime_payload = execution.model_dump(mode="python")
    if runtime_payload.get("method") != "GET":
        findings.append("live CSV execution method is not GET")
    if runtime_payload.get("retry_count") != 0:
        findings.append("live CSV execution reports a retry")
    if runtime_payload.get("network_executed") is not True:
        findings.append("live CSV execution does not affirm network execution")
    if runtime_payload.get("documents_downloaded") is not False:
        findings.append("live CSV execution reports CEQA document downloads")
    if runtime_payload.get("persistence_mutated") is not False:
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


def _execution_from_observation(
    request: CeqanetCsvExportRequest,
    observation: BoundedHttpObservation,
    *,
    max_retained_rows: int,
    executed_at: datetime | None,
) -> CeqanetCsvLiveExecution:
    complete = observation.failure_kind is HttpFailureKind.NONE
    retained_body = observation.response_body if complete else b""
    error = observation.error_type
    if observation.failure_kind is HttpFailureKind.OVERSIZED_RESPONSE:
        error = "response_exceeds_max_body_bytes"
    inspection: CeqanetCsvInspection | None = None
    inspection_error: str | None = None
    if observation.status_code == 200 and complete:
        inspection, inspection_error = _inspect_complete_body(
            request,
            retained_body,
            content_type=observation.content_type,
            max_retained_rows=max_retained_rows,
        )
    return _build_execution(
        request=request,
        final_url=observation.final_url,
        status_code=observation.status_code,
        content_type=observation.content_type,
        content_disposition=None,
        observed_body_length=observation.response_size,
        retained_body=retained_body,
        retained_complete=complete,
        error=error,
        inspection=inspection,
        inspection_error=inspection_error,
        executed_at=executed_at,
    )


def _inspect_complete_body(
    request: CeqanetCsvExportRequest,
    body: bytes,
    *,
    content_type: str | None,
    max_retained_rows: int,
) -> tuple[CeqanetCsvInspection | None, str | None]:
    try:
        return (
            inspect_ceqanet_csv_bytes(
                request,
                body,
                content_type=content_type,
                max_retained_rows=max_retained_rows,
            ),
            None,
        )
    except ValueError as exc:
        return None, str(exc)


def _build_execution(
    *,
    request: CeqanetCsvExportRequest,
    final_url: str,
    status_code: int | None,
    content_type: str | None,
    content_disposition: str | None,
    observed_body_length: int,
    retained_body: bytes,
    retained_complete: bool,
    error: str | None,
    inspection: CeqanetCsvInspection | None,
    inspection_error: str | None,
    executed_at: datetime | None,
) -> CeqanetCsvLiveExecution:
    digest_body = retained_body if retained_complete else b""
    payload: dict[str, Any] = {
        "request": request,
        "request_url": request.source_url,
        "final_url": final_url,
        "status_code": status_code,
        "content_type": content_type,
        "content_disposition": content_disposition,
        "observed_body_byte_length": observed_body_length,
        "retained_body_base64": base64.b64encode(retained_body).decode("ascii"),
        "retained_body_byte_length": len(retained_body),
        "retained_body_complete": retained_complete,
        "body_sha256": hashlib.sha256(digest_body).hexdigest(),
        "error": error,
        "inspection": inspection,
        "inspection_error": inspection_error,
        "executed_at": executed_at or datetime.now(UTC),
    }
    draft = CeqanetCsvLiveExecution(
        **payload,
        execution_digest="0" * 64,
    )
    return draft.model_copy(update={"execution_digest": draft.computed_digest()})
