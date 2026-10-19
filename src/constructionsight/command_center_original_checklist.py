"""Exact retained-source manual observation review using the original offline service.

This is an in-memory checklist report, not source verification, registry
promotion, remote access, persistence or commercial authorization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.command_center_source_plans import original_offline_source_plans
from constructionsight.command_center_source_reachability import (
    _selected_original_source,
    _source_digest,
)
from constructionsight.operator_services.source_registry_persistence_service import (
    persist_authorized_source_registry_records,
)
from constructionsight.operator_services.source_registry_service import (
    apply_authorized_source_registry_update_plan,
)
from constructionsight.source_registry_update_plan_models import SourceRegistryUpdatePlanReport
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_source_observation_templates,
    build_source_verification_checklist_report,
)
from constructionsight.storage.database import create_private_database_engine

_OBSERVATION_FLAGS = frozenset({
    "public_entry_observed",
    "query_behavior_observed",
    "result_list_observed",
    "detail_page_observed",
    "access_barrier_observed",
    "terms_review_observed",
})
_OBSERVATION_FIELDS = _OBSERVATION_FLAGS | frozenset({
    "source_key", "source_name", "notes", "evidence_refs",
})


def preview_original_manual_checklist(
    database: Path | None, *, source_name: str, public_url: str,
) -> dict[str, Any]:
    """Read one retained source and its original blank operator template."""
    source = _selected_original_source(database, source_name, public_url)
    template = build_source_observation_templates([source])[0]
    return {
        "schema_version": "constructionsight.original-manual-checklist-preview/v1",
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "source_key": template.source_key,
        "expected_source_sha256": _source_digest(source),
        "original_observation_template": template.model_dump(mode="json"),
        "network_executed": False,
        "original_registry_mutated": False,
        "source_promoted": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Unfilled manual observation template for an exact original source. "
            "No public HTTP access, source promotion or verification is inferred."
        ),
    }


def review_original_manual_checklist(
    database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Project explicitly entered manual evidence through the original builder."""
    if set(payload) != {
        "source_name", "public_url", "expected_source_sha256",
        "review_reason", "caller_confirmation", "observation",
    }:
        raise ValueError("exact original manual review request fields required")
    reason = payload["review_reason"]
    expected = payload["expected_source_sha256"]
    if (
        not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
        or not isinstance(expected, str) or len(expected) != 64
        or any(c not in "0123456789abcdef" for c in expected)
    ):
        raise ValueError("explicit review reason and current source receipt required")
    source = _selected_original_source(
        database, payload["source_name"], payload["public_url"],
    )
    if _source_digest(source) != expected:
        raise ValueError("original source changed; repeat manual observation review")
    template = build_source_observation_templates([source])[0]
    data = payload["observation"]
    if not isinstance(data, dict) or set(data) != _OBSERVATION_FIELDS:
        raise ValueError("complete exact original manual observation fields required")
    if data["source_key"] != template.source_key or data["source_name"] != source.source_name:
        raise ValueError("manual observation does not belong to this original source")
    if any(
        data[field] is not None and type(data[field]) is not bool
        for field in _OBSERVATION_FLAGS
    ):
        raise ValueError("manual observation flags must be true, false or unknown")
    notes = data["notes"]
    if notes is not None and (
        not isinstance(notes, str) or len(notes) > 2000
        or any(ord(c) < 32 and c not in "\n\t" for c in notes)
    ):
        raise ValueError("manual observation notes are invalid")
    refs = data["evidence_refs"]
    if (
        not isinstance(refs, list) or len(refs) > 20
        or any(
            not isinstance(ref, str) or not 1 <= len(ref) <= 300
            or any(ord(c) < 32 or ord(c) == 127 for c in ref)
            for ref in refs
        )
        or len(refs) != len(set(refs))
    ):
        raise ValueError("unique bounded manual evidence references required")
    if any(data[field] is True for field in _OBSERVATION_FLAGS) and not refs:
        raise ValueError("positive manual observations require evidence references")
    observation = SourceVerificationObservation.model_validate(data)
    checklist = build_source_verification_checklist_report(
        [source], default_adapter_family_specs(),
        check_http=False, observations=[observation],
    )
    plans = original_offline_source_plans([source], observations=[observation])
    return {
        "schema_version": "constructionsight.original-manual-checklist-review/v1",
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "reviewed_source_sha256": expected,
        "review_reason": reason.strip(),
        "original_manual_checklist": checklist.to_dict(),
        "original_promotion_plan": plans["original_promotion_plan"],
        "original_registry_update_plan": plans["original_registry_update_plan"],
        "original_operator_observation": observation.model_dump(mode="json"),
        "network_executed": False,
        "original_registry_mutated": False,
        "source_promoted": False,
        "commercial_authority_granted": False,
        "operator_observations_not_independent_verification": True,
        "meaning": (
            "Original manual checklist report for operator-supplied observations. "
            "No independent corroboration, registry update or authority is implied."
        ),
    }


def apply_reviewed_original_source_registry_update(
    database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Apply one exact manually reviewed original status through both original guards.

    Rebuild the original plan; never accept a caller-supplied source row or status.
    The persistence guard rechecks the complete source under its SQLite writer lock.
    """
    review_fields = {
        "source_name", "public_url", "expected_source_sha256",
        "review_reason", "caller_confirmation", "observation",
    }
    if set(payload) != review_fields | {
        "expected_plan_digest", "apply_reason", "apply_confirmation",
    }:
        raise ValueError("exact original registry approval fields required")
    reason = payload["apply_reason"]
    if (
        payload["apply_confirmation"] is not True
        or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or not isinstance(payload["expected_plan_digest"], str)
        or len(payload["expected_plan_digest"]) != 64
        or any(c not in "0123456789abcdef" for c in payload["expected_plan_digest"])
    ):
        raise ValueError("explicit exact-plan registry approval required")
    reviewed = review_original_manual_checklist(
        database, {field: payload[field] for field in review_fields},
    )
    plan = SourceRegistryUpdatePlanReport.model_validate(
        reviewed["original_registry_update_plan"]
    )
    if (
        plan.update_count != 1
        or len(plan.rows) != 1
        or plan.plan_digest != payload["expected_plan_digest"]
    ):
        raise ValueError("approved original source update plan is absent or stale")
    source = _selected_original_source(
        database, payload["source_name"], payload["public_url"],
    )
    if _source_digest(source) != payload["expected_source_sha256"]:
        raise ValueError("original source changed after review; review again")
    if database is None:
        raise ValueError("original operator database is not configured")
    approved = apply_authorized_source_registry_update_plan(
        [source],
        plan,
        expected_plan_digest=plan.plan_digest,
        expected_registry_digest=plan.registry_digest,
        target_path_identity=str(database.absolute()),
        caller_confirmation=True,
        authorization_reason=reason.strip(),
    )
    engine = create_private_database_engine(database, create=False)
    try:
        with Session(engine, autoflush=False) as session:
            persisted = persist_authorized_source_registry_records(
                session, list(approved.sources),
                caller_confirmation=True,
                authorization_reason=reason.strip(),
                expected_current_source=source,
            )
    finally:
        engine.dispose()
    resulting_status = approved.sources[0].verification_status.value
    return {
        "schema_version": "constructionsight.original-source-registry-reviewed-apply/v1",
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "reviewed_source_sha256": payload["expected_source_sha256"],
        "approved_plan_digest": plan.plan_digest,
        "original_registry_apply_report": approved.report.to_dict(),
        "original_registry_persistence_report": persisted.report.model_dump(mode="json"),
        "apply_authorization": approved.authorization.to_dict(),
        "persistence_authorization": persisted.authorization.to_dict(),
        "resulting_verification_status": resulting_status,
        "original_registry_mutated": True,
        "network_executed": False,
        "live_collection_authorized": False,
        "commercial_authority_granted": False,
        "independent_source_verification_established": False,
        "meaning": (
            "One reviewed original verification-status change was persisted. "
            "Manual evidence is not independent corroboration, and this does not "
            "authorize recurring collection, contact, outreach, or bidding."
        ),
    }
