"""Read-only original CEQAnet CSV maturity/replay review in the native console.

An operator-pinned, already retained execution and the same existing original
source registry are independently checked. Nothing here authorizes source access,
creates an access policy, collects more evidence, or promotes verification status.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_service import (
    build_ceqanet_csv_encoding_replay,
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_maturity_proposal_service import (
    build_ceqanet_source_maturity_proposal,
    verify_ceqanet_source_maturity_proposal,
)
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.orm import SourceRecord
from constructionsight.storage.runtime_artifacts import read_runtime_artifact
from constructionsight.storage.source_registry import SourceRegistryStore

_MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
_MAX_SOURCES = 2_000


def original_retained_ceqanet_maturity(
    database: Path | None, retained_execution: Path | None,
) -> dict[str, Any]:
    """Independently derive original replay and keep-partial maturity from retained data."""
    if database is None or retained_execution is None:
        return {
            "schema_version": "constructionsight.native-original-ceqanet-maturity/v1",
            "available": False,
            "configured": False,
            "read_only": True,
            "network_executed": False,
            "persistence_mutated": False,
            "registry_promoted": False,
            "reason": (
                "Select the existing --operator-database and "
                "--operator-ceqanet-csv-evidence at launch."
            ),
        }
    if database.is_symlink() or not database.is_file():
        raise ValueError("original CEQAnet maturity requires an existing operator database")
    raw = read_runtime_artifact(retained_execution, max_bytes=_MAX_ARTIFACT_BYTES)
    payload: Any = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("original CEQAnet retained execution must be a JSON object")
    # The native import has its own original discovery-binding check. Never
    # reinterpret an unverified bound-capture envelope as independent proof.
    if payload.get("schema_version") == "ceqanet_bound_project_capture.v1":
        raise ValueError("bound CEQAnet capture requires separate original discovery proof")
    execution = CeqanetCsvLiveExecution.model_validate(payload)
    execution.assert_integrity()
    replay = build_ceqanet_csv_encoding_replay(execution, max_retained_rows=1_000)
    replay_verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    if not replay_verification.passed:
        raise ValueError("original retained CEQAnet CSV replay failed verification")
    if execution.inspection is not None and execution.inspection != replay.inspection:
        raise ValueError("retained CEQAnet CSV inspection disagrees with original replay")
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            count = session.scalar(select(func.count()).select_from(SourceRecord)) or 0
            if count > _MAX_SOURCES:
                raise ValueError("original source registry exceeds the bounded review limit")
            sources = SourceRegistryStore(session).list_sources()
            if len(sources) != count:
                raise ValueError("original source registry changed during maturity review")
            original_registry_digest = source_registry_digest(sources)
        proposal = build_ceqanet_source_maturity_proposal(
            sources, execution, replay, replay_verification,
        )
        verification = verify_ceqanet_source_maturity_proposal(
            sources, execution, replay, replay_verification, proposal,
        )
        if not verification.passed:
            raise ValueError("original CEQAnet source maturity verification failed")
        if read_runtime_artifact(
            retained_execution, max_bytes=_MAX_ARTIFACT_BYTES,
        ) != raw:
            raise ValueError("original CEQAnet retained execution changed during review")
        # Independently re-open the original registry rather than relying on a
        # stale session cache. A concurrent registry edit invalidates the result.
        with Session(engine, autoflush=False) as session:
            current = SourceRegistryStore(session).list_sources()
            if (
                len(current) != count
                or source_registry_digest(current) != original_registry_digest
            ):
                raise ValueError("original source registry changed during maturity review")
    finally:
        engine.dispose()
    return {
        "schema_version": "constructionsight.native-original-ceqanet-maturity/v1",
        "available": True,
        "configured": True,
        "retained_artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "original_source_registry_digest": original_registry_digest,
        "original_execution_digest": execution.execution_digest,
        "original_replay_digest": replay.replay_digest,
        "original_replay_verification": replay_verification.model_dump(mode="json"),
        "original_maturity_proposal": proposal.model_dump(mode="json"),
        "original_maturity_verification": verification.model_dump(mode="json"),
        "observed_encoding": replay.inspection.encoding,
        "observed_row_count": replay.inspection.row_count,
        "read_only": True,
        "network_executed": False,
        "persistence_mutated": False,
        "registry_promoted": False,
        "access_policy_authorized": False,
        "recurring_collection_authorized": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Original offline keep-partial maturity evidence only. One retained "
            "response is not a verified recurring access policy or permission to "
            "promote source status, schedule downloads, qualify leads or send outreach."
        ),
    }
