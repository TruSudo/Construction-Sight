"""Native access to the original append-only normalized source candidate docket.

Reuses original exact-source preflight, authorization and atomic staging.
Staged evidence is NOT a scored lead, project identity decision or outreach.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from constructionsight.operator_dashboard_models import RecordKind
from constructionsight.source_candidate_docket_service import (
    CandidateDocketError,
    list_staged_source_candidates,
    preview_source_for_docket,
    stage_authorized_source_candidate,
)


def _target(database: Path | None, kind: str, record_id: str) -> tuple[Path, RecordKind]:
    if database is None or database.is_symlink() or not database.is_file():
        raise ValueError("existing original operator database required for source docket")
    if not isinstance(kind, str) or kind not in {"ceqa", "permit"}:
        raise ValueError("original docket accepts only CEQA or permit source records")
    if (
        not isinstance(record_id, str)
        or not 1 <= len(record_id) <= 255
        or record_id != record_id.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in record_id)
    ):
        raise ValueError("select one exact stored source record identifier")
    return database, cast(RecordKind, kind)


def preview_original_source_docket(
    database: Path | None, *, kind: str, record_id: str,
) -> dict[str, Any]:
    """Return exact original candidate preview and integrity-checked existing stages."""
    database, source_kind = _target(database, kind, record_id)
    try:
        preview = preview_source_for_docket(
            database, kind=source_kind, record_id=record_id,
        )
    except LookupError as exc:
        raise ValueError("exact original source record not found") from exc
    try:
        entries = list_staged_source_candidates(
            database, kind=source_kind, record_id=record_id, limit=50,
        )
        ready = True
    except CandidateDocketError as exc:
        if "docket table is absent" not in str(exc):
            raise
        entries = []
        ready = False
    return {
        "schema_version": "constructionsight.native-original-source-docket/v1",
        "source_kind": source_kind,
        "source_record_id": record_id,
        "original_source_preview": preview.model_dump(mode="json"),
        "original_staged_history": [
            entry.model_dump(mode="json") for entry in entries
        ],
        "history_limit": 50,
        "docket_schema_ready": ready,
        "may_request_staging": ready,
        "network_executed": False,
        "source_record_mutated": False,
        "commercial_lead_created": False,
        "outreach_authorized": False,
        "bid_authorized": False,
        "meaning": (
            "Original normalized append-only source-review evidence only; neither "
            "staging nor previous docket entries approve a site, source fact or lead."
        ),
    }


def stage_reviewed_original_source_docket(
    database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Explicitly stage only the reviewed original exact source/preview digest."""
    if set(payload) != {
        "kind", "record_id", "expected_preview_id",
        "expected_source_sha256", "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact original source docket approval fields required")
    database, source_kind = _target(
        database, payload["kind"], payload["record_id"]
    )
    reason = payload["review_reason"]
    if (
        not isinstance(reason, str) or reason != reason.strip()
        or not 10 <= len(reason) <= 1000
        or payload["caller_confirmation"] is not True
        or not isinstance(payload["expected_preview_id"], str)
        or not isinstance(payload["expected_source_sha256"], str)
    ):
        raise ValueError("exact unapproved review staging requires explicit confirmation")
    original = stage_authorized_source_candidate(
        database,
        kind=source_kind,
        record_id=payload["record_id"],
        expected_preview_id=payload["expected_preview_id"],
        expected_source_sha256=payload["expected_source_sha256"],
        reason=reason,
        caller_confirmation=True,
    )
    return {
        "schema_version": "constructionsight.native-original-source-docket-stage/v1",
        "original_stage_entry": original.entry.model_dump(mode="json"),
        "original_authorization": original.authorization.to_dict(),
        "network_executed": False,
        "source_record_mutated": False,
        "staged_recorded_new": original.entry.recorded_new,
        "commercial_lead_created": False,
        "outreach_authorized": False,
        "bid_authorized": False,
        "meaning": (
            "One exact normalized source observation is staged for future human "
            "review. No record has been promoted, qualified or sent externally."
        ),
    }
