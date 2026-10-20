"""Durable, explicitly reviewed retention of one original source checklist.

The original offline manual review supplies the evidence and plans. This native
handoff retains a private, create-only immutable snapshot, without modifying
source status, legal access assumptions, source network state or commerce.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.command_center_original_checklist import (
    review_original_manual_checklist,
)
from constructionsight.storage.runtime_artifacts import write_runtime_text

_SCHEMA = "constructionsight.original-checklist-retention-preview/v1"
_REVIEW_KEYS = frozenset({
    "source_name", "public_url", "expected_source_sha256",
    "review_reason", "caller_confirmation", "observation",
})
_MAX_OUTPUT_BYTES = 4 * 1024 * 1024


def _material(reviewed: dict[str, Any]) -> dict[str, Any]:
    """Stable original evidence content excludes only builder wall-clock times."""
    checklist = dict(reviewed["original_manual_checklist"])
    checklist.pop("generated_at", None)
    rows: list[dict[str, Any]] = []
    for row in checklist["rows"]:
        clean_row = dict(row)
        clean_row.pop("generated_at", None)
        rows.append(clean_row)
    checklist["rows"] = rows
    return {
        "source_name": reviewed["source_name"],
        "public_url": reviewed["public_url"],
        "source_sha256": reviewed["reviewed_source_sha256"],
        "original_operator_observation": reviewed["original_operator_observation"],
        "review_reason": reviewed["review_reason"],
        "original_manual_checklist": checklist,
        "original_promotion_plan_digest": (
            reviewed["original_promotion_plan"]["plan_digest"]
        ),
        "original_registry_update_plan_digest": (
            reviewed["original_registry_update_plan"]["plan_digest"]
        ),
    }


def preview_original_manual_checklist_retention(
    database: Path | None,
    private_folder: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Rebuild the original checklist and select one stable private artifact."""
    if not isinstance(payload, dict) or set(payload) != _REVIEW_KEYS:
        raise ValueError("exact original manual checklist review is required")
    if database is None or private_folder is None:
        return {
            "schema_version": _SCHEMA,
            "available": False,
            "may_request_approval": False,
            "reason": "select a real source database and private native data folder",
            "network_executed": False,
            "source_registry_mutated": False,
            "retained_evidence_written": False,
        }
    reviewed = review_original_manual_checklist(database, payload)
    material = _material(reviewed)
    digest = authorization_digest(
        "native-original-source-manual-evidence-retention/v1", material,
    )
    filename = f"original-source-checklist-{digest}.json"
    destination = private_folder / "source-verification-evidence" / filename
    blockers: list[str] = []
    if destination.exists() or destination.is_symlink():
        blockers.append("exact reviewed source checklist evidence already retained")
    return {
        "schema_version": _SCHEMA,
        "available": True,
        "may_request_approval": not blockers,
        "blockers": blockers,
        "source_name": reviewed["source_name"],
        "public_url": reviewed["public_url"],
        "source_sha256": reviewed["reviewed_source_sha256"],
        "original_manual_checklist_status": (
            reviewed["original_manual_checklist"]["rows"][0]["checklist_status"]
        ),
        "evidence_references": reviewed["original_operator_observation"]["evidence_refs"],
        "original_plan_digest": material["original_registry_update_plan_digest"],
        "expected_review_digest": digest,
        "relative_retained_file": "source-verification-evidence/" + filename,
        "network_executed": False,
        "source_registry_mutated": False,
        "retained_evidence_written": False,
        "independent_verification_established": False,
        "commercial_authority_granted": False,
    }


def retain_reviewed_original_manual_checklist(
    database: Path | None,
    private_folder: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Publish the exact original review as a create-only retained artifact."""
    if not isinstance(payload, dict) or set(payload) != _REVIEW_KEYS | {
        "expected_review_digest", "retention_reason", "retention_confirmation",
    }:
        raise ValueError("exact original checklist retention confirmation required")
    reason = payload["retention_reason"]
    if (
        payload["retention_confirmation"] is not True
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2_000
        or not isinstance(payload["expected_review_digest"], str)
    ):
        raise ValueError("explicit reviewed evidence-retention consent required")
    selected = {key: payload[key] for key in _REVIEW_KEYS}
    preview = preview_original_manual_checklist_retention(
        database, private_folder, selected,
    )
    if (
        not preview["may_request_approval"]
        or preview["expected_review_digest"] != payload["expected_review_digest"]
    ):
        raise ValueError("original manual checklist proof is already retained or stale")
    assert database is not None
    assert private_folder is not None
    reviewed = review_original_manual_checklist(database, selected)
    if authorization_digest(
        "native-original-source-manual-evidence-retention/v1", _material(reviewed),
    ) != preview["expected_review_digest"]:
        raise ValueError("source checklist changed before evidence publication")
    contents = {
        "schema_version": "constructionsight.original-checklist-retained-evidence/v1",
        "reviewed_at_utc": datetime.now(UTC).isoformat(),
        "review_digest": preview["expected_review_digest"],
        "retention_reason": reason.strip(),
        "original_review": reviewed,
        "source_registry_mutated": False,
        "network_executed": False,
        "independent_verification_established": False,
        "commercial_authority_granted": False,
    }
    text = json.dumps(contents, indent=2, sort_keys=True) + "\n"
    relative = preview["relative_retained_file"]
    destination = private_folder / relative
    write_runtime_text(
        destination, text, overwrite=False, max_bytes=_MAX_OUTPUT_BYTES,
    )
    return {
        "schema_version": "constructionsight.original-checklist-retention-receipt/v1",
        "source_name": reviewed["source_name"],
        "source_sha256": reviewed["reviewed_source_sha256"],
        "retained_review_digest": preview["expected_review_digest"],
        "retained_artifact_ref": relative,
        "retained_artifact_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "retained_evidence_written": True,
        "source_registry_mutated": False,
        "network_executed": False,
        "source_promoted": False,
        "independent_verification_established": False,
        "recurring_collection_authorized": False,
        "commercial_authority_granted": False,
    }
