"""Original policy-bound CEQAnet CSV one-shot evidence handoff from the native GUI.

Read-only preview is required. The accepted effect uses the *original* governed
evidence executor, with original daily allowance and independent ledger checks.
The result is create-only retained evidence, not a ledger mutation or schedule.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_csv_access_policy_models import CeqanetCsvAccessPolicy
from constructionsight.ceqanet_csv_access_policy_service import (
    verify_ceqanet_csv_access_policy,
)
from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
    CeqanetCsvEvidenceSeries,
    CeqanetCsvEvidenceSeriesStatus,
)
from constructionsight.ceqanet_csv_evidence_series_service import (
    EvidenceExecutionInput,
    execute_ceqanet_csv_evidence_request,
    verify_ceqanet_csv_evidence_series,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_service import (
    build_ceqanet_csv_encoding_replay,
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_csv_service import build_ceqanet_csv_export_request
from constructionsight.ceqanet_maturity_proposal_service import (
    build_ceqanet_source_maturity_proposal,
    verify_ceqanet_source_maturity_proposal,
)
from constructionsight.command_center_ceqanet_acquisition import _profile
from constructionsight.command_center_ceqanet_series_audit import (
    _json_artifact,
    _relative_artifact,
    original_retained_ceqanet_series_audit,
)
from constructionsight.legal import AccessDecision, evaluate_access
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.runtime_artifacts import write_runtime_text
from constructionsight.storage.source_registry import SourceRegistryStore

_MAX_OUTPUT_BYTES = 16 * 1024 * 1024
_REQUEST_KEYS = {"export", "access_review"}


def _request_fields(payload: dict[str, Any]) -> tuple[str, int | None]:
    export = payload.get("export")
    if not isinstance(export, dict) or set(export) != {"sch_number", "document_id"}:
        raise ValueError("exact SCH and optional document identity required")
    sch, document = export["sch_number"], export["document_id"]
    if not isinstance(sch, str) or len(sch) != 10 or not sch.isascii() or not sch.isdigit():
        raise ValueError("original evidence SCH must have exactly ten ASCII digits")
    if document is not None and (
        type(document) is not int or not 1 <= document <= 2_147_483_647
    ):
        raise ValueError("original document identity must be a positive bounded integer")
    return sch, document


def _context(
    database: Path | None,
    original_execution_path: Path | None,
    policy_path: Path | None,
    manifest_path: Path | None,
) -> tuple[dict[str, Any], tuple[Any, ...], CeqanetCsvEvidenceSeries, list[EvidenceExecutionInput]]:
    """Load verified original inputs anew and bind them to the native audit."""
    audit = original_retained_ceqanet_series_audit(
        database, original_execution_path, policy_path, manifest_path,
    )
    if not audit["available"]:
        raise ValueError("configure an original retained CEQAnet evidence series first")
    assert database is not None
    assert original_execution_path is not None
    assert policy_path is not None
    assert manifest_path is not None

    manifest, _ = _json_artifact(manifest_path, limit=64 * 1024)
    series, _ = _json_artifact(_relative_artifact(manifest_path.parent, manifest["series_file"]))
    raw_execution, _ = _json_artifact(original_execution_path)
    raw_policy, _ = _json_artifact(policy_path)
    execution = CeqanetCsvLiveExecution.model_validate(raw_execution)
    policy = CeqanetCsvAccessPolicy.model_validate(raw_policy)
    current_series = CeqanetCsvEvidenceSeries.model_validate(series)
    if (
        current_series.series_digest != audit["series"]["series_digest"]
        or policy.policy_digest != audit["original_policy_digest"]
    ):
        raise ValueError("original series or access policy changed after audit")
    observed: list[EvidenceExecutionInput] = []
    for item in manifest["evidence_executions"]:
        content, _ = _json_artifact(_relative_artifact(manifest_path.parent, item["file"]))
        observed.append((
            item["artifact_ref"], CeqanetCsvEvidenceExecution.model_validate(content),
        ))
    replay = build_ceqanet_csv_encoding_replay(execution, max_retained_rows=1_000)
    replay_verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            sources = SourceRegistryStore(session).list_sources()
            if source_registry_digest(sources) != audit["original_registry_digest"]:
                raise ValueError("original source registry changed after series audit")
    finally:
        engine.dispose()
    maturity = build_ceqanet_source_maturity_proposal(
        sources, execution, replay, replay_verification,
    )
    maturity_verification = verify_ceqanet_source_maturity_proposal(
        sources, execution, replay, replay_verification, maturity,
    )
    policy_verification = verify_ceqanet_csv_access_policy(
        sources, execution, replay, replay_verification, maturity,
        maturity_verification, policy,
    )
    verification = verify_ceqanet_csv_evidence_series(
        sources, execution, replay, replay_verification, maturity,
        maturity_verification, policy, policy_verification, observed, current_series,
    )
    if not verification.passed:
        raise ValueError("original evidence series changed during native preflight")
    return (
        audit,
        (
            sources, execution, replay, replay_verification, maturity,
            maturity_verification, policy, policy_verification,
        ),
        current_series,
        observed,
    )


def preview_original_ceqanet_series_request(
    database: Path | None,
    original_execution_path: Path | None,
    policy_path: Path | None,
    manifest_path: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Prove an exact still-current one-shot boundary without source or file writes."""
    if not isinstance(payload, dict) or set(payload) != _REQUEST_KEYS:
        raise ValueError("exact original CEQAnet series request and access review required")
    sch, document = _request_fields(payload)
    request = build_ceqanet_csv_export_request(
        sch_number=sch, document_id=document,
    )
    profile = _profile(request.source_url, payload["access_review"])
    access = evaluate_access(profile)
    if any(value is None for value in (
        database, original_execution_path, policy_path, manifest_path,
    )):
        return {
            "schema_version": (
                "constructionsight.native-ceqanet-series-execution-preview/v1"
            ),
            "available": False,
            "configured": False,
            "may_request_approval": False,
            "blockers": [
                "configure an original retained CEQAnet evidence series first"
            ],
            "network_executed": False,
            "persistence_mutated": False,
            "series_advanced": False,
            "commercial_authority_granted": False,
        }
    audit, original, series, _observed = _context(
        database, original_execution_path, policy_path, manifest_path,
    )
    policy = original[6]
    assert isinstance(policy, CeqanetCsvAccessPolicy)
    now_date = datetime.now(UTC).date()
    day = now_date.isoformat()
    file_name = (
        f"ceqanet-csv-evidence-{day}-{sch}-"
        f"{'project' if document is None else 'document-'+str(document)}.json"
    )
    assert manifest_path is not None
    output = manifest_path.parent / file_name
    blockers: list[str] = []
    if access.decision is not AccessDecision.ALLOWED:
        blockers.append("independent current source access review denied or incomplete")
    if audit["policy_date_window_state"] != "date_window_current":
        blockers.append("original source access policy is not current in UTC")
    if series.status is not CeqanetCsvEvidenceSeriesStatus.COLLECTING:
        blockers.append("original evidence series is not collecting")
    if now_date in (item.utc_date for item in series.observations):
        blockers.append("a retained original series observation already exists today")
    if request.export_kind not in policy.allowed_export_kinds:
        blockers.append("the exact export scope is outside the original policy")
    if output.is_symlink() or output.exists():
        blockers.append("retained execution output is already occupied")
    expected = authorization_digest(
        "native-ceqanet-original-series-execution",
        {
            "request": request.model_dump(mode="json"),
            "access_review": payload["access_review"],
            "source_registry_digest": audit["original_registry_digest"],
            "policy_digest": audit["original_policy_digest"],
            "series_digest": series.series_digest,
            "manifest_sha256": audit["manifest_sha256"],
            "series_artifact_sha256": audit["series_artifact_sha256"],
            "original_execution_sha256": audit["retained_execution_sha256"],
            "evidence_digests": audit["retained_execution_sha256"],
            "authorized_utc_date": day,
            "retained_output_file": file_name,
        },
    )
    return {
        "schema_version": "constructionsight.native-ceqanet-series-execution-preview/v1",
        "available": True,
        "configured": True,
        "original_request": request.model_dump(mode="json"),
        "original_policy_digest": policy.policy_digest,
        "original_series_digest": series.series_digest,
        "original_series_status": series.status.value,
        "original_series_sequence": series.series_sequence,
        "original_policy_date_window_state": audit["policy_date_window_state"],
        "access_decision": access.decision.value,
        "access_reason": access.reason,
        "retained_output_file": file_name,
        "authorized_utc_date": day,
        "blockers": blockers,
        "may_request_approval": not blockers,
        "expected_preview_digest": expected,
        "network_executed": False,
        "persistence_mutated": False,
        "series_advanced": False,
        "commercial_authority_granted": False,
    }


def execute_reviewed_original_ceqanet_series_request(
    database: Path | None,
    original_execution_path: Path | None,
    policy_path: Path | None,
    manifest_path: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute original guarded one-shot effect only after exact native consent."""
    if not isinstance(payload, dict) or set(payload) != _REQUEST_KEYS | {
        "expected_preview_digest", "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact original policy-bound execution approval required")
    reason = payload["review_reason"]
    if (
        payload["caller_confirmation"] is not True
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2_000
        or not isinstance(payload["expected_preview_digest"], str)
    ):
        raise ValueError("explicit original CEQAnet evidence approval required")
    selected = {key: payload[key] for key in _REQUEST_KEYS}
    preview = preview_original_ceqanet_series_request(
        database, original_execution_path, policy_path, manifest_path, selected,
    )
    if (
        not preview["may_request_approval"]
        or preview["expected_preview_digest"] != payload["expected_preview_digest"]
    ):
        raise ValueError("original CEQAnet policy-bound authorization denied or stale")
    audit, original, series, observed = _context(
        database, original_execution_path, policy_path, manifest_path,
    )
    if (
        audit["original_policy_digest"] != preview["original_policy_digest"]
        or series.series_digest != preview["original_series_digest"]
    ):
        raise ValueError("original evidence series changed before authorized operation")
    sch, document = _request_fields(selected)
    request = build_ceqanet_csv_export_request(
        sch_number=sch, document_id=document,
    )
    assert manifest_path is not None
    output = manifest_path.parent / preview["retained_output_file"]
    if output.is_symlink() or output.exists():
        raise ValueError("original retained evidence output is already occupied")
    # This original service—not a new HTTP client—owns the permanent UTC-date
    # allowance, original one-shot authorization, independent live verification,
    # redirect/retry controls and effect replay protection.
    execution = execute_ceqanet_csv_evidence_request(
        *original,
        series,
        observed,
        request,
        execute_live=True,
        max_retained_rows=1_000,
        authorization_reason=reason.strip(),
    )
    execution.assert_integrity()
    payload_text = json.dumps(
        execution.model_dump(mode="json"), indent=2, sort_keys=True,
    )
    write_runtime_text(
        output, payload_text + "\n", overwrite=False, max_bytes=_MAX_OUTPUT_BYTES,
    )
    # Do not mutate the separately verified manifest/append-only series. The
    # operator must explicitly review and advance that original ledger.
    return {
        "schema_version": "constructionsight.native-ceqanet-series-execution-result/v1",
        "original_policy_digest": execution.policy_digest,
        "original_series_digest": series.series_digest,
        "evidence_execution_digest": execution.evidence_execution_digest,
        "original_live_verification": execution.live_verification.model_dump(mode="json"),
        "retained_artifact_file": output.name,
        "retained_artifact_sha256": hashlib.sha256(
            (payload_text + "\n").encode("utf-8")
        ).hexdigest(),
        "reviewed_preview_digest": preview["expected_preview_digest"],
        "network_executed": True,
        "retained_evidence_written": True,
        "series_advanced": False,
        "registry_promoted": False,
        "recurring_collection_authorized": False,
        "commercial_authority_granted": False,
    }
