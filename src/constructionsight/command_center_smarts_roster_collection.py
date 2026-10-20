"""Reviewed native entry point to the original exact SMARTS roster collector.

No automatic collection. Reuses the existing checkpointed/journalled roster
implementation for one bounded manual run after an exact lawful-access review.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import httpx

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.command_center_ceqanet_acquisition import _profile
from constructionsight.legal import AccessDecision, evaluate_access
from constructionsight.smarts_api import API_URL, USER_AGENT, fetch_exact_facility
from constructionsight.smarts_collection import (
    CollectionResult,
    _roster_digest,
    collect_roster,
    parse_roster,
)
from constructionsight.smarts_evidence_ledger import verify_smarts_journal
from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_SCHEMA = "constructionsight.native-original-smarts-collection-preview/v1"
_REVIEW_KEYS = {"run_id", "max_requests", "access_review"}


def _exact_paths(
    roster_path: Path | None,
    journal_path: Path | None,
    checkpoint_path: Path | None,
) -> tuple[Path, Path, Path] | None:
    if any(x is None for x in (roster_path, journal_path, checkpoint_path)):
        return None
    assert roster_path is not None
    assert journal_path is not None
    assert checkpoint_path is not None
    paths = (roster_path, journal_path, checkpoint_path)
    if len({p.absolute() for p in paths}) != 3:
        raise ValueError("SMARTS original roster, journal and checkpoint must differ")
    if checkpoint_path.is_symlink() or (
        checkpoint_path.exists() and not checkpoint_path.is_file()
    ):
        raise ValueError("original SMARTS checkpoint must be a regular file or new path")
    if journal_path.is_symlink() or (
        journal_path.exists() and not journal_path.is_file()
    ):
        raise ValueError("original SMARTS evidence journal must be a regular file")
    return paths


def _reviewed_fields(payload: dict[str, Any]) -> tuple[str, int]:
    if not isinstance(payload, dict) or set(payload) != _REVIEW_KEYS:
        raise ValueError("exact SMARTS roster source review required")
    run_id, budget = payload["run_id"], payload["max_requests"]
    if not isinstance(run_id, str) or re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", run_id,
    ) is None:
        raise ValueError("original SMARTS run ID must be canonical and bounded")
    if type(budget) is not int or not 1 <= budget <= 25:
        raise ValueError("original SMARTS maximum requests must be between 1 and 25")
    return run_id, budget


def preview_original_smarts_roster_collection(
    roster_path: Path | None,
    journal_path: Path | None,
    checkpoint_path: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Bind one explicit source roster and request budget, without any effects."""
    run_id, budget = _reviewed_fields(payload)
    profile = _profile(API_URL, payload["access_review"])
    access = evaluate_access(profile)
    configured = _exact_paths(roster_path, journal_path, checkpoint_path)
    if configured is None:
        return {
            "schema_version": _SCHEMA,
            "configured": False,
            "available": False,
            "may_request_approval": False,
            "blockers": [
                "select an exact original SMARTS roster, journal and checkpoint at launch"
            ],
            "network_executed": False,
            "checkpoint_created": False,
            "journal_mutated": False,
        }
    roster, journal, checkpoint = configured
    raw = read_runtime_artifact(roster, max_bytes=8_192)
    targets = parse_roster(raw)
    if budget > len(targets):
        raise ValueError("SMARTS request budget exceeds selected exact roster")
    journal_state = "new"
    if journal.is_file():
        verify_smarts_journal(journal, read_only=True)
        journal_state = "original_journal_verified"
    checkpoint_state = "new" if not checkpoint.exists() else "existing"
    blockers = []
    if access.decision is not AccessDecision.ALLOWED:
        blockers.append("independent current SMARTS source access facts are not allowed")
    if not journal.parent.is_dir() or not checkpoint.parent.is_dir():
        blockers.append("original source journal or checkpoint parent directory missing")
    if read_runtime_artifact(roster, max_bytes=8_192) != raw:
        raise ValueError("selected original SMARTS roster changed during review")
    digest = authorization_digest(
        "native-original-smarts-roster-manual-approval",
        {
            "run_id": run_id,
            "roster_sha256": hashlib.sha256(raw).hexdigest(),
            "original_roster_digest": _roster_digest(targets),
            "roster_count": len(targets),
            "source_url": API_URL,
            "access_review": payload["access_review"],
            "max_requests": budget,
            "journal_path": str(journal.absolute()),
            "checkpoint_path": str(checkpoint.absolute()),
        },
    )
    return {
        "schema_version": _SCHEMA,
        "configured": True,
        "available": True,
        "run_id": run_id,
        "original_roster_digest": _roster_digest(targets),
        "roster_sha256": hashlib.sha256(raw).hexdigest(),
        "roster_count": len(targets),
        "exact_request_budget": budget,
        "journal_state": journal_state,
        "checkpoint_state": checkpoint_state,
        "access_decision": access.decision.value,
        "access_reason": access.reason,
        "blockers": blockers,
        "may_request_approval": not blockers,
        "expected_preview_digest": digest,
        "network_executed": False,
        "checkpoint_created": False,
        "journal_mutated": False,
        "schedule_activated": False,
        "commercial_authority_granted": False,
    }


def execute_reviewed_original_smarts_roster_collection(
    roster_path: Path | None,
    journal_path: Path | None,
    checkpoint_path: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Call the unchanged checkpointed original collector only after consent."""
    if not isinstance(payload, dict) or set(payload) != _REVIEW_KEYS | {
        "expected_preview_digest", "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact approved original SMARTS roster sweep required")
    reason = payload["review_reason"]
    if (
        payload["caller_confirmation"] is not True
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2_000
        or not isinstance(payload["expected_preview_digest"], str)
    ):
        raise ValueError("explicit original SMARTS roster collection approval required")
    selected = {name: payload[name] for name in _REVIEW_KEYS}
    preview = preview_original_smarts_roster_collection(
        roster_path, journal_path, checkpoint_path, selected,
    )
    if (
        not preview["may_request_approval"]
        or preview["expected_preview_digest"] != payload["expected_preview_digest"]
    ):
        raise ValueError("SMARTS roster source access denied or stale approval")
    configured = _exact_paths(roster_path, journal_path, checkpoint_path)
    assert configured is not None
    roster, journal, checkpoint = configured
    raw = read_runtime_artifact(roster, max_bytes=8_192)
    if hashlib.sha256(raw).hexdigest() != preview["roster_sha256"]:
        raise ValueError("original exact roster changed before source request")
    targets = parse_roster(raw)
    with httpx.Client(
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        result: CollectionResult = collect_roster(
            run_id=preview["run_id"],
            targets=targets,
            journal_path=journal,
            checkpoint_path=checkpoint,
            max_requests=preview["exact_request_budget"],
            fetch=lambda target: fetch_exact_facility(
                client,
                county=target.county,
                app_id=target.app_id,
                wdid=target.wdid,
            ),
        )
    verified = verify_smarts_journal(journal, read_only=True)
    return {
        "schema_version": "constructionsight.native-original-smarts-collection-result/v1",
        "run_id": result.run_id,
        "completed": result.completed,
        "total": result.total,
        "original_request_count": result.requests,
        "first_observations": result.first_observations,
        "changed": result.changed,
        "unchanged": result.unchanged,
        "original_journal_verification": verified,
        "roster_sha256": preview["roster_sha256"],
        "original_roster_digest": preview["original_roster_digest"],
        "reviewed_preview_digest": preview["expected_preview_digest"],
        "network_executed": result.requests > 0,
        "original_evidence_retained": True,
        "checkpoint_updated": True,
        "schedule_activated": False,
        "source_registry_mutated": False,
        "commercial_authority_granted": False,
    }
