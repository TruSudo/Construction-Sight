"""Offline native audit of original CEQAnet recurring-run definition and manifest.

Existing registry, checklist, definition and exact-window manifest are verified
through original source services. This audit cannot execute, schedule, retry,
create a new definition or grant current source permission.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunManifest,
    CeqanetRunReadiness,
)
from constructionsight.ceqanet_recurring_run_service import (
    assert_ceqanet_definition_evidence_current,
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.orm import SourceRecord
from constructionsight.storage.runtime_artifacts import read_runtime_artifact
from constructionsight.storage.source_registry import SourceRegistryStore

_LIMIT = 16 * 1024 * 1024
_SOURCE_LIMIT = 2_000
_CHECKLIST_LIMIT = 2_000
_SCHEMA = "constructionsight.native-original-ceqanet-recurring-audit/v1"


def _retained_model(path: Path, model: Any) -> tuple[Any, bytes]:
    raw = read_runtime_artifact(path, max_bytes=_LIMIT)
    value: Any = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("original recurring-run input must be a JSON object")
    return model.model_validate(value), raw


def original_retained_ceqanet_recurring_audit(
    database: Path | None,
    checklist_path: Path | None,
    definition_path: Path | None,
    manifest_path: Path | None,
) -> dict[str, Any]:
    """Independently re-evaluate original bounded one-window run governance."""
    if any(x is None for x in (
        database, checklist_path, definition_path, manifest_path,
    )):
        return {
            "schema_version": _SCHEMA,
            "available": False,
            "configured": False,
            "ready_for_foreground_attempt": False,
            "read_only": True,
            "network_executed": False,
            "schedule_activated": False,
            "reason": (
                "Select --operator-database, --operator-ceqanet-recurring-checklist, "
                "--operator-ceqanet-recurring-definition and "
                "--operator-ceqanet-recurring-manifest at launch."
            ),
        }
    assert database is not None
    assert checklist_path is not None
    assert definition_path is not None
    assert manifest_path is not None

    checklist, raw_checklist = _retained_model(
        checklist_path, SourceVerificationChecklistReport,
    )
    definition, raw_definition = _retained_model(
        definition_path, CeqanetRecurringRunDefinition,
    )
    manifest, raw_manifest = _retained_model(
        manifest_path, CeqanetRecurringRunManifest,
    )
    assert isinstance(checklist, SourceVerificationChecklistReport)
    assert isinstance(definition, CeqanetRecurringRunDefinition)
    assert isinstance(manifest, CeqanetRecurringRunManifest)
    if checklist.source_count != len(checklist.rows):
        raise ValueError("original checklist source count does not match rows")
    if checklist.source_count > _CHECKLIST_LIMIT:
        raise ValueError("original checklist exceeds bounded source count")
    if checklist.status_counts != dict(Counter(
        row.checklist_status.value for row in checklist.rows
    )):
        raise ValueError("original checklist status summary does not match rows")
    definition.assert_integrity()
    manifest.assert_integrity()

    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            count = session.scalar(select(func.count()).select_from(SourceRecord)) or 0
            if count > _SOURCE_LIMIT:
                raise ValueError("original registry exceeds bounded source count")
            sources = SourceRegistryStore(session).list_sources()
            if len(sources) != count:
                raise ValueError("original source registry count changed during audit")
        rebuilt = build_ceqanet_recurring_run_definition(
            sources,
            checklist,
            source_key=definition.source_key,
            query_template=definition.query_template,
            access_assumptions=definition.access_assumptions,
            execution_base_url=definition.execution_base_url,
            timeout_seconds=definition.timeout_seconds,
            max_body_chars=definition.max_body_chars,
        )
        if (
            rebuilt.definition_digest != definition.definition_digest
            or rebuilt.approval_payload() != definition.approval_payload()
        ):
            raise ValueError("original recurring definition differs from current evidence")
        recalculated_manifest = build_ceqanet_recurring_run_manifest(
            definition,
            window_start=manifest.window_start,
            window_end=manifest.window_end,
        )
        if (
            recalculated_manifest.manifest_digest != manifest.manifest_digest
            or recalculated_manifest.approval_payload() != manifest.approval_payload()
        ):
            raise ValueError("original recurring manifest differs from exact definition")
        blockers = list(definition.blockers)
        if definition.readiness is CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION:
            assert_ceqanet_definition_evidence_current(
                definition, sources, checklist,
            )
        else:
            blockers.append("original definition is blocked for manual execution")
        if manifest.readiness is not CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION:
            blockers.append("original exact-window manifest is blocked")
        for path, raw in (
            (checklist_path, raw_checklist),
            (definition_path, raw_definition),
            (manifest_path, raw_manifest),
        ):
            if read_runtime_artifact(path, max_bytes=_LIMIT) != raw:
                raise ValueError("original recurring evidence changed during audit")
        with Session(engine, autoflush=False) as session:
            after = SourceRegistryStore(session).list_sources()
            if len(after) != count or after != sources:
                raise ValueError("source registry changed during recurring review")
    finally:
        engine.dispose()

    return {
        "schema_version": _SCHEMA,
        "available": True,
        "configured": True,
        "source_key": definition.source_key,
        "run_id": manifest.run_id,
        "definition_digest": definition.definition_digest,
        "manifest_digest": manifest.manifest_digest,
        "checklist_sha256": hashlib.sha256(raw_checklist).hexdigest(),
        "definition_sha256": hashlib.sha256(raw_definition).hexdigest(),
        "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
        "original_definition_verified": True,
        "original_manifest_verified": True,
        "original_readiness": definition.readiness.value,
        "original_manifest_readiness": manifest.readiness.value,
        "window_start": manifest.window_start.isoformat(),
        "window_end": manifest.window_end.isoformat(),
        "window_field": manifest.window_field.value,
        "original_query": manifest.query,
        "source_verification_blockers": blockers,
        "ready_for_foreground_attempt": not blockers,
        "original_persistence_authorized": manifest.persistence_authorized,
        "original_operator_live_authorization_required": (
            manifest.operator_live_authorization_required
        ),
        "read_only": True,
        "network_executed": False,
        "persistence_mutated": False,
        "schedule_activated": False,
        "background_recurring_execution_authorized": False,
        "manual_execution_performed": False,
        "commercial_authority_granted": False,
        "meaning": (
            "The original exact-window manifest and current registry/checklist "
            "agree. Readiness does not grant present lawful source access, "
            "automatic recurrence, scheduled execution, or any outbound activity."
        ),
    }
