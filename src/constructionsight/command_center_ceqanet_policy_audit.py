"""Offline original CEQAnet access-policy verification, without activation.

This verifies an operator-pinned historical policy against the current original
source registry and separately retained source evidence. A valid or in-date
policy is never treated as proof of actual current source permission.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.ceqanet_csv_access_policy_models import CeqanetCsvAccessPolicy
from constructionsight.ceqanet_csv_access_policy_service import (
    assert_ceqanet_csv_access_policy_current,
    verify_ceqanet_csv_access_policy,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_service import (
    build_ceqanet_csv_encoding_replay,
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_maturity_proposal_service import (
    build_ceqanet_source_maturity_proposal,
    verify_ceqanet_source_maturity_proposal,
)
from constructionsight.command_center_ceqanet_maturity import (
    original_retained_ceqanet_maturity,
)
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.orm import SourceRecord
from constructionsight.storage.runtime_artifacts import read_runtime_artifact
from constructionsight.storage.source_registry import SourceRegistryStore

_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_SOURCES = 2_000


def original_retained_ceqanet_policy_audit(
    database: Path | None,
    retained_execution: Path | None,
    retained_policy: Path | None,
) -> dict[str, Any]:
    """Review one immutable original policy without creating any source authority."""
    name = "constructionsight.native-original-ceqanet-policy-audit/v1"
    if database is None or retained_execution is None or retained_policy is None:
        return {
            "schema_version": name,
            "configured": False,
            "available": False,
            "read_only": True,
            "network_executed": False,
            "policy_activated": False,
            "reason": (
                "Select --operator-database, --operator-ceqanet-csv-evidence and "
                "--operator-ceqanet-csv-access-policy at launch."
            ),
        }
    # Reuse the existing native offline maturity/replay/registry preflight.
    maturity_audit = original_retained_ceqanet_maturity(database, retained_execution)
    if maturity_audit.get("original_maturity_verification", {}).get("passed") is not True:
        raise ValueError("original CEQAnet maturity verification is required")
    raw_policy = read_runtime_artifact(retained_policy, max_bytes=_MAX_ARTIFACT_BYTES)
    policy_payload: Any = json.loads(raw_policy.decode("utf-8"))
    if not isinstance(policy_payload, dict):
        raise ValueError("original CEQAnet policy must be a JSON object")
    policy = CeqanetCsvAccessPolicy.model_validate(policy_payload)
    policy.assert_integrity()

    raw_execution = read_runtime_artifact(
        retained_execution, max_bytes=_MAX_ARTIFACT_BYTES,
    )
    if hashlib.sha256(raw_execution).hexdigest() != maturity_audit[
        "retained_artifact_sha256"
    ]:
        raise ValueError("original CEQAnet retained execution changed during policy audit")
    execution = CeqanetCsvLiveExecution.model_validate(
        json.loads(raw_execution.decode("utf-8"))
    )
    execution.assert_integrity()
    replay = build_ceqanet_csv_encoding_replay(execution, max_retained_rows=1_000)
    replay_verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    if not replay_verification.passed:
        raise ValueError("original CEQAnet replay verification is required")

    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            count = session.scalar(select(func.count()).select_from(SourceRecord)) or 0
            if count > _MAX_SOURCES:
                raise ValueError("original source registry exceeds bounded review limit")
            sources = SourceRegistryStore(session).list_sources()
            digest = source_registry_digest(sources)
            if len(sources) != count or digest != maturity_audit[
                "original_source_registry_digest"
            ]:
                raise ValueError("original source registry changed during policy audit")
        proposal = build_ceqanet_source_maturity_proposal(
            sources, execution, replay, replay_verification,
        )
        maturity_verification = verify_ceqanet_source_maturity_proposal(
            sources, execution, replay, replay_verification, proposal,
        )
        if (
            not maturity_verification.passed
            or proposal.proposal_digest
            != maturity_audit["original_maturity_proposal"]["proposal_digest"]
        ):
            raise ValueError("original maturity evidence changed during policy audit")

        policy_verification = verify_ceqanet_csv_access_policy(
            sources,
            execution,
            replay,
            replay_verification,
            proposal,
            maturity_verification,
            policy,
        )
        today = datetime.now(UTC).date()
        window_state = "not_verified"
        if policy_verification.passed:
            try:
                assert_ceqanet_csv_access_policy_current(policy, as_of_date=today)
            except ValueError:
                window_state = (
                    "not_yet_effective"
                    if today < policy.effective_date else "expired"
                )
            else:
                window_state = "date_window_current"

        if read_runtime_artifact(
            retained_execution, max_bytes=_MAX_ARTIFACT_BYTES,
        ) != raw_execution:
            raise ValueError("original CEQAnet execution changed during policy review")
        if read_runtime_artifact(
            retained_policy, max_bytes=_MAX_ARTIFACT_BYTES,
        ) != raw_policy:
            raise ValueError("original CEQAnet policy changed during policy review")
        with Session(engine, autoflush=False) as session:
            current = SourceRegistryStore(session).list_sources()
            if (
                len(current) != count
                or source_registry_digest(current) != digest
            ):
                raise ValueError("original registry changed during policy verification")
    finally:
        engine.dispose()

    return {
        "schema_version": name,
        "configured": True,
        "available": True,
        "retained_policy_sha256": hashlib.sha256(raw_policy).hexdigest(),
        "retained_execution_sha256": hashlib.sha256(raw_execution).hexdigest(),
        "registry_digest": digest,
        "original_policy": policy.model_dump(mode="json"),
        "original_policy_verification": policy_verification.model_dump(mode="json"),
        "policy_integrity_verified": True,
        "registry_and_source_evidence_verified": policy_verification.passed,
        "as_of_utc_date": today.isoformat(),
        "date_window_state": window_state,
        "read_only": True,
        "network_executed": False,
        "persistence_mutated": False,
        "policy_created": False,
        "policy_activated": False,
        "registry_promoted": False,
        "access_to_remote_source_confirmed": False,
        "recurring_collection_authorized": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Historical offline original access-policy review only. Even an "
            "evidence-matching date-window-current policy is not current legal "
            "permission, production activation, background scheduling, source "
            "promotion, outreach, or bidding authority."
        ),
    }
