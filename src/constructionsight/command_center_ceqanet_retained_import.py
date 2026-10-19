"""Original CEQAnet retained CSV evidence -> guarded operator persistence.

Only an explicitly configured retained artifact is eligible; never accept arbitrary
browser-provided evidence bytes or a destination path. This uses the original CSV
replay, bound discovery proof, atomic write and read-back services.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session
from typer import BadParameter

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import canonical_digest
from constructionsight.ceqanet_csv_operator_bridge import (
    ReviewedCeqanetCsvBridge,
    build_reviewed_ceqanet_csv_bridge,
)
from constructionsight.ceqanet_csv_operator_bridge_cli import (
    _load_bound_capture_candidate,
)
from constructionsight.operator_dashboard import build_dashboard_snapshot
from constructionsight.operator_services.ceqanet_persistence_service import (
    execute_authorized_ceqanet_write_plan,
)
from constructionsight.storage.database import (
    database_url_from_path,
    prepare_private_database,
)
from constructionsight.storage.domain_store import CeqaStore
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.runtime_artifacts import read_runtime_artifact


def _replay(
    evidence_path: Path,
    listing_path: Path | None,
    queue_path: Path | None,
) -> tuple[ReviewedCeqanetCsvBridge, str, bool]:
    """Read one pinned retained file, then revalidate any bound listing lineage."""
    raw = read_runtime_artifact(evidence_path, max_bytes=16 * 1024 * 1024)
    payload: Any = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("configured CEQAnet evidence must be a JSON object")
    content = payload.get("live_execution", payload)
    if not isinstance(content, dict):
        raise ValueError("original CSV live execution must be an object")
    execution = CeqanetCsvLiveExecution.model_validate(content)
    bridge = build_reviewed_ceqanet_csv_bridge(execution)
    bound = payload.get("schema_version") == "ceqanet_bound_project_capture.v1"
    if bound:
        discovery = payload.get("discovery_binding")
        if not isinstance(discovery, dict) or listing_path is None or queue_path is None:
            raise ValueError("bound CEQAnet capture requires both original listing proofs")
        sch = discovery.get("sch_number")
        county = discovery.get("source_claimed_county")
        if not isinstance(sch, str) or not isinstance(county, str):
            raise ValueError("bound CEQAnet discovery identity is malformed")
        try:
            original = _load_bound_capture_candidate(
                listing_evidence=listing_path,
                queue_evidence=queue_path,
                sch_number=sch,
            )
        except BadParameter as exc:
            raise ValueError(f"original bound CEQAnet proof rejected: {exc}") from exc
        if original != discovery:
            raise ValueError("bound discovery evidence is stale or substituted")
        if any(
            row.state_clearinghouse_number != sch or row.county != county
            for row in bridge.preview.ceqa_records
        ):
            raise ValueError("CSV row disagrees with reviewed listing/queue lineage")
    elif "discovery_binding" in payload:
        raise ValueError("discovery binding requires original bound-capture envelope")
    return bridge, hashlib.sha256(raw).hexdigest(), bound


def _destination_identity(database: Path) -> str:
    path = prepare_private_database(database, create=False)
    info = path.lstat()
    return authorization_digest("native-retained-ceqanet-import-destination", {
        "path": str(path), "device": info.st_dev, "inode": info.st_ino,
    })


def preview_retained_ceqanet_import(
    database: Path | None,
    evidence: Path | None,
    listing: Path | None,
    queue: Path | None,
) -> dict[str, Any]:
    """Rebuild original write plan offline and prove existing native read compatibility."""
    if evidence is None:
        return {
            "schema_version": "constructionsight.native-retained-csv-import/v1",
            "configured": False,
            "available": False,
            "network_executed": False,
            "persistence_mutated": False,
            "reason": "Configure one existing original CSV evidence artifact at startup.",
        }
    if database is None:
        raise ValueError("original operator database is required for retained CSV import")
    identity = _destination_identity(database)
    engine = create_operator_read_engine(database)
    engine.dispose()
    bridge, artifact_sha, bound = _replay(evidence, listing, queue)
    return {
        "schema_version": "constructionsight.native-retained-csv-import/v1",
        "configured": True,
        "available": True,
        "retained_artifact_sha256": artifact_sha,
        "source_sha256": bridge.source_sha256,
        "source_execution_digest": bridge.source_execution_digest,
        "source_inspection_digest": bridge.source_inspection_digest,
        "expected_write_plan_digest": canonical_digest(bridge.write_plan.to_dict()),
        "expected_destination_identity": identity,
        "original_write_plan": bridge.write_plan.to_dict(),
        "source_record_keys": list(bridge.source_record_keys),
        "planned_write_count": bridge.write_plan.operation_count,
        "discovery_binding_verified": bound,
        "network_executed": False,
        "persistence_mutated": False,
        "source_claims_verified": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Offline verified retained original CSV plan. Each source row remains "
            "unassessed; a separate exact approval is required before atomic writes."
        ),
    }


def apply_reviewed_retained_ceqanet_import(
    database: Path | None,
    evidence: Path | None,
    listing: Path | None,
    queue: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Revalidate exact artifact and database, authorize atomic original write, read back."""
    if set(payload) != {
        "retained_artifact_sha256", "source_sha256",
        "expected_write_plan_digest", "expected_destination_identity",
        "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact original retained CSV import approval required")
    reason = payload["review_reason"]
    if (not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
            or payload["caller_confirmation"] is not True):
        raise ValueError("explicit reviewed retained CSV import reason required")
    if database is None or evidence is None:
        raise ValueError("configured original CSV evidence and database are required")
    preview = preview_retained_ceqanet_import(database, evidence, listing, queue)
    if any(
        not isinstance(payload[key], str) or payload[key] != preview[key]
        for key in (
            "retained_artifact_sha256", "source_sha256",
            "expected_write_plan_digest", "expected_destination_identity",
        )
    ):
        raise ValueError("reviewed original CSV artifact, plan or database has changed")
    bridge, artifact_sha, bound = _replay(evidence, listing, queue)
    if (artifact_sha != payload["retained_artifact_sha256"]
            or canonical_digest(bridge.write_plan.to_dict())
            != payload["expected_write_plan_digest"]
            or _destination_identity(database) != payload["expected_destination_identity"]):
        raise ValueError("original retained source changed before approved persistence")
    try:
        approved = execute_authorized_ceqanet_write_plan(
            write_plan_payload=bridge.write_plan.to_dict(),
            database_url=database_url_from_path(database),
            caller_confirmation=True,
            authorization_reason=reason.strip(),
        )
    except AuthorizationDeniedError as exc:
        raise ValueError(f"original CEQAnet persistence denied: {exc}") from exc
    if approved.execution.applied_count != bridge.write_plan.operation_count:
        raise ValueError("atomic original persistence did not apply the exact operation count")
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            store = CeqaStore(session)
            for expected in bridge.preview.ceqa_records:
                actual = store.get(expected.ceqa_key)
                if (
                    actual is None or actual.title != expected.title
                    or not actual.provenance or not expected.provenance
                    or actual.provenance[0].raw_reference
                    != expected.provenance[0].raw_reference
                ):
                    raise ValueError("native original imported source readback mismatch")
            sch_set = {
                record.state_clearinghouse_number
                for record in bridge.preview.ceqa_records
            }
            if len(sch_set) != 1 or None in sch_set:
                raise ValueError("original CSV reviewed project has no single SCH identity")
            source_sch = next(iter(sch_set))
            dashboard = build_dashboard_snapshot(
                session, kind="ceqa", query=source_sch, limit=500,
            )
            visible = {item.record_id for item in dashboard.projects}
            if not set(bridge.source_record_keys).issubset(visible):
                raise ValueError("native source investigation dashboard missing imported rows")
    finally:
        engine.dispose()
    return {
        "schema_version": "constructionsight.native-retained-csv-applied/v1",
        "retained_artifact_sha256": artifact_sha,
        "source_sha256": bridge.source_sha256,
        "approved_plan_digest": payload["expected_write_plan_digest"],
        "applied_operations": approved.execution.applied_count,
        "original_authorization": approved.authorization.to_dict(),
        "discovery_binding_verified": bound,
        "operator_readback_verified": True,
        "operator_dashboard_visibility_verified": True,
        "source_record_keys": list(bridge.source_record_keys),
        "network_executed": False,
        "persistence_mutated": True,
        "source_claims_verified": False,
        "commercial_authority_granted": False,
        "meaning": (
            "One original authorized atomic import is visible in the existing native "
            "domain store. All imported observations remain unassessed source claims."
        ),
    }
