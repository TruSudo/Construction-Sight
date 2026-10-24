"""One explicitly reviewed native foreground CEQAnet manifest attempt.

No scheduler or invented source access. Uses the original durable effect/attempt
allowance, exact-window runner and independent original execution verifier.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunManifest,
)
from constructionsight.ceqanet_recurring_run_verifier import (
    verify_ceqanet_recurring_run_execution,
)
from constructionsight.command_center_ceqanet_acquisition import _profile
from constructionsight.command_center_ceqanet_recurring_audit import (
    _retained_model,
    original_retained_ceqanet_recurring_audit,
)
from constructionsight.legal import AccessDecision, evaluate_access
from constructionsight.operator_services.ceqanet_recurring_run_service import (
    execute_authorized_ceqanet_recurring_run,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.runtime_artifacts import write_runtime_text
from constructionsight.storage.source_registry import SourceRegistryStore

_MAX_OUTPUT = 16 * 1024 * 1024
_REVIEW_KEYS = {"attempt_sequence", "access_review"}
_SCHEMA = "constructionsight.native-ceqanet-recurring-attempt-preview/v1"


def _attempt_number(payload: dict[str, Any]) -> int:
    number = payload["attempt_sequence"]
    if type(number) is not int or not 1 <= number <= 1_000:
        raise ValueError("original recurring-run manual attempt must be 1–1000")
    return number


def preview_original_ceqanet_recurring_attempt(
    database: Path | None,
    checklist_path: Path | None,
    definition_path: Path | None,
    manifest_path: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Confirm exact current source evidence, original window and output scope."""
    if not isinstance(payload, dict) or set(payload) != _REVIEW_KEYS:
        raise ValueError("exact original manifest attempt and access facts required")
    attempt = _attempt_number(payload)
    if any(path is None for path in (
        database, checklist_path, definition_path, manifest_path,
    )):
        return {
            "schema_version": _SCHEMA,
            "available": False,
            "may_request_approval": False,
            "blockers": ["configure exact original CEQAnet recurring evidence first"],
            "network_executed": False,
            "persistence_mutated": False,
            "schedule_activated": False,
        }
    audit = original_retained_ceqanet_recurring_audit(
        database, checklist_path, definition_path, manifest_path,
    )
    assert manifest_path is not None
    assert definition_path is not None
    assert checklist_path is not None
    definition, _ = _retained_model(
        definition_path, CeqanetRecurringRunDefinition,
    )
    manifest, _ = _retained_model(manifest_path, CeqanetRecurringRunManifest)
    assert isinstance(definition, CeqanetRecurringRunDefinition)
    assert isinstance(manifest, CeqanetRecurringRunManifest)
    profile = _profile(manifest.execution_base_url, payload["access_review"])
    access = evaluate_access(profile)
    filename = f"ceqanet-recurring-{manifest.run_id}-attempt-{attempt:04d}.json"
    target = manifest_path.parent / filename
    blockers: list[str] = list(audit["source_verification_blockers"])
    if not audit["ready_for_foreground_attempt"]:
        blockers.append("original recurring manifest is not ready for manual execution")
    if access.decision is not AccessDecision.ALLOWED:
        blockers.append("independent current lawful source-access review is not allowed")
    if target.is_symlink() or target.exists():
        blockers.append("the original manifest attempt already has a retained output")
    return {
        "schema_version": _SCHEMA,
        "available": True,
        "attempt_sequence": attempt,
        "run_id": manifest.run_id,
        "definition_digest": definition.definition_digest,
        "manifest_digest": manifest.manifest_digest,
        "window_start": audit["window_start"],
        "window_end": audit["window_end"],
        "source_key": audit["source_key"],
        "access_decision": access.decision.value,
        "access_reason": access.reason,
        "original_readiness": audit["original_manifest_readiness"],
        "retained_output_file": filename,
        "blockers": blockers,
        "may_request_approval": not blockers,
        "expected_preview_digest": authorization_digest(
            "native-ceqanet-original-manual-recurring-approval",
            {
                "attempt_sequence": attempt,
                "access_review": payload["access_review"],
                "source_key": audit["source_key"],
                "definition_digest": audit["definition_digest"],
                "manifest_digest": audit["manifest_digest"],
                "checklist_sha256": audit["checklist_sha256"],
                "definition_sha256": audit["definition_sha256"],
                "manifest_sha256": audit["manifest_sha256"],
                "output": filename,
            },
        ),
        "network_executed": False,
        "persistence_mutated": False,
        "schedule_activated": False,
        "commercial_authority_granted": False,
    }


def execute_reviewed_original_ceqanet_recurring_attempt(
    database: Path | None,
    checklist_path: Path | None,
    definition_path: Path | None,
    manifest_path: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Invoke only the unchanged durable original per-attempt authorized effect."""
    if not isinstance(payload, dict) or set(payload) != _REVIEW_KEYS | {
        "expected_preview_digest", "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact positive original recurring-manifest approval required")
    reason = payload["review_reason"]
    if (
        payload["caller_confirmation"] is not True
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2_000
        or not isinstance(payload["expected_preview_digest"], str)
    ):
        raise ValueError("explicit operator authorization for one foreground attempt required")
    approved_selection = {name: payload[name] for name in _REVIEW_KEYS}
    reviewed = preview_original_ceqanet_recurring_attempt(
        database, checklist_path, definition_path, manifest_path, approved_selection,
    )
    if (
        not reviewed["may_request_approval"]
        or reviewed["expected_preview_digest"] != payload["expected_preview_digest"]
    ):
        raise ValueError("original recurring-run approval is blocked or stale")
    assert database is not None
    assert checklist_path is not None
    assert definition_path is not None
    assert manifest_path is not None

    # Verify the exact retained governance artifacts again before the owned
    # effect; the original executor also independently checks current evidence.
    audit = original_retained_ceqanet_recurring_audit(
        database, checklist_path, definition_path, manifest_path,
    )
    if (
        audit["manifest_digest"] != reviewed["manifest_digest"]
        or audit["definition_digest"] != reviewed["definition_digest"]
    ):
        raise ValueError("original manifest evidence changed after approved preview")
    checklist, _ = _retained_model(
        checklist_path, SourceVerificationChecklistReport,
    )
    definition, _ = _retained_model(
        definition_path, CeqanetRecurringRunDefinition,
    )
    manifest, _ = _retained_model(
        manifest_path, CeqanetRecurringRunManifest,
    )
    assert isinstance(checklist, SourceVerificationChecklistReport)
    assert isinstance(definition, CeqanetRecurringRunDefinition)
    assert isinstance(manifest, CeqanetRecurringRunManifest)
    output = manifest_path.parent / reviewed["retained_output_file"]
    if output.is_symlink() or output.exists():
        raise ValueError("original retained attempt output already occupied")
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            sources = SourceRegistryStore(session).list_sources()
    finally:
        engine.dispose()
    # The original effect-consumption service enforces a cross-process one-shot
    # allowance for this exact run-id/manifest/attempt. No new HTTP client.
    result = execute_authorized_ceqanet_recurring_run(
        definition=definition,
        manifest=manifest,
        sources=sources,
        checklist_report=checklist,
        attempt_sequence=_attempt_number(payload),
        caller_confirmation=True,
        authorization_reason=reason.strip(),
    )
    original = result.execution
    original.assert_integrity()
    verification = verify_ceqanet_recurring_run_execution(
        definition, manifest, original, sources, checklist,
    )
    if not verification.passed:
        raise ValueError("original recurring execution failed independent verification")
    text = json.dumps(
        original.model_dump(mode="json"), sort_keys=True, indent=2,
    ) + "\n"
    write_runtime_text(
        output, text, overwrite=False, max_bytes=_MAX_OUTPUT,
    )
    return {
        "schema_version": "constructionsight.native-ceqanet-recurring-attempt-result/v1",
        "run_id": original.run_id,
        "attempt_id": original.attempt_id,
        "attempt_sequence": original.attempt_sequence,
        "manifest_digest": original.manifest_digest,
        "execution_digest": original.execution_digest,
        "original_verification": verification.model_dump(mode="json"),
        "reviewed_preview_digest": reviewed["expected_preview_digest"],
        "retained_output_file": output.name,
        "retained_output_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "network_executed": original.network_executed,
        "retained_evidence_written": True,
        "persistence_mutated": False,
        "schedule_activated": False,
        "background_recurring_execution_authorized": False,
        "commercial_authority_granted": False,
    }
