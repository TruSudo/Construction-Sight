"""Build and verify offline CEQAnet CSV encoding replay artifacts."""

from __future__ import annotations

import hashlib

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_csv_service import inspect_ceqanet_csv_bytes


def build_ceqanet_csv_encoding_replay(
    execution: CeqanetCsvLiveExecution,
    *,
    max_retained_rows: int = 1_000,
) -> CeqanetCsvEncodingReplay:
    """Derive one offline inspection from the exact retained live response bytes."""

    execution.assert_integrity()
    if execution.status_code != 200:
        raise ValueError("encoding replay requires an HTTP 200 live execution")
    if execution.error is not None:
        raise ValueError("encoding replay requires a live execution without network error")
    if not execution.retained_body_complete:
        raise ValueError("encoding replay requires the complete retained response body")
    if execution.documents_downloaded:
        raise ValueError("encoding replay refuses document-download evidence")
    if execution.persistence_mutated:
        raise ValueError("encoding replay refuses persistence-mutating evidence")
    if max_retained_rows < 0:
        raise ValueError("max_retained_rows cannot be negative")

    body = execution.retained_body_bytes()
    if len(body) != execution.observed_body_byte_length:
        raise ValueError("retained response length does not match the live execution")
    if hashlib.sha256(body).hexdigest() != execution.body_sha256:
        raise ValueError("retained response SHA-256 does not match the live execution")

    inspection = inspect_ceqanet_csv_bytes(
        execution.request,
        body,
        content_type=execution.content_type,
        max_retained_rows=max_retained_rows,
    )
    draft = CeqanetCsvEncodingReplay(
        source_execution_digest=execution.execution_digest,
        source_body_sha256=execution.body_sha256,
        source_body_byte_length=execution.observed_body_byte_length,
        source_request_url=execution.request_url,
        source_status_code=execution.status_code,
        inspection=inspection,
        replay_digest="0" * 64,
    )
    replay = draft.model_copy(update={"replay_digest": draft.computed_digest()})
    replay.assert_integrity()
    return replay


def verify_ceqanet_csv_encoding_replay(
    execution: CeqanetCsvLiveExecution,
    replay: CeqanetCsvEncodingReplay,
) -> CeqanetCsvEncodingReplayVerification:
    """Independently verify replay provenance and recompute the offline inspection."""

    findings: list[str] = []
    try:
        execution.assert_integrity()
    except ValueError as exc:
        findings.append(str(exc))
    try:
        replay.assert_integrity()
    except ValueError as exc:
        findings.append(str(exc))

    if replay.source_execution_digest != execution.execution_digest:
        findings.append("replay source execution digest does not match the live execution")
    if replay.source_body_sha256 != execution.body_sha256:
        findings.append("replay source body SHA-256 does not match the live execution")
    if replay.source_body_byte_length != execution.observed_body_byte_length:
        findings.append("replay source byte length does not match the live execution")
    if replay.source_request_url != execution.request_url:
        findings.append("replay source URL does not match the live execution")
    if replay.source_status_code != execution.status_code:
        findings.append("replay source status does not match the live execution")
    network_executed = _widen_bool(replay.network_executed)
    persistence_mutated = _widen_bool(replay.persistence_mutated)
    if network_executed:
        findings.append("encoding replay reports network execution")
    if persistence_mutated:
        findings.append("encoding replay reports persistence mutation")

    try:
        body = execution.retained_body_bytes()
        recomputed = inspect_ceqanet_csv_bytes(
            execution.request,
            body,
            content_type=execution.content_type,
            max_retained_rows=replay.inspection.retained_row_count,
        )
    except ValueError as exc:
        findings.append(f"encoding replay recomputation failed: {exc}")
    else:
        if recomputed != replay.inspection:
            findings.append("replay inspection does not match retained response bytes")
        try:
            recomputed.assert_integrity()
        except ValueError as exc:
            findings.append(str(exc))

    return CeqanetCsvEncodingReplayVerification(
        passed=not findings,
        finding_count=len(findings),
        findings=findings,
        source_execution_digest=execution.execution_digest,
        source_body_sha256=execution.body_sha256,
        inspection_digest=replay.inspection.inspection_digest,
        replay_digest=replay.replay_digest,
    )


def _widen_bool(value: bool) -> bool:
    return value
