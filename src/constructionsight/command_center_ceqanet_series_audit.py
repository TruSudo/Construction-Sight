"""Read-only original CEQAnet governed CSV evidence-series verification.

One operator-pinned private manifest names a bounded snapshot and exact retained
execution artifacts inside its own directory. This does not run, resume, or
schedule source collection and never mints an access policy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from constructionsight.ceqanet_csv_access_policy_models import CeqanetCsvAccessPolicy
from constructionsight.ceqanet_csv_access_policy_service import verify_ceqanet_csv_access_policy
from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
    CeqanetCsvEvidenceSeries,
)
from constructionsight.ceqanet_csv_evidence_series_service import (
    EvidenceExecutionInput,
    verify_ceqanet_csv_evidence_series,
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
from constructionsight.command_center_ceqanet_policy_audit import (
    original_retained_ceqanet_policy_audit,
)
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.runtime_artifacts import (
    read_runtime_artifact,
    runtime_artifact_parts,
)
from constructionsight.storage.source_registry import SourceRegistryStore

_MAX_JSON_BYTES = 16 * 1024 * 1024
_MAX_MANIFEST_BYTES = 64 * 1024
_MAX_SERIES_EXECUTIONS = 31
_MAX_TOTAL_EXECUTION_BYTES = 64 * 1024 * 1024
_MANIFEST_VERSION = "constructionsight.ceqanet_csv_series_manifest.v1"
_SCHEMA = "constructionsight.native-original-ceqanet-series-audit/v1"


def _relative_artifact(root: Path, name: str) -> Path:
    if not isinstance(name, str):
        raise ValueError("original evidence-series path must be a relative artifact name")
    return root.joinpath(*runtime_artifact_parts(name))


def _json_artifact(path: Path, *, limit: int = _MAX_JSON_BYTES) -> tuple[dict[str, Any], bytes]:
    raw = read_runtime_artifact(path, max_bytes=limit)
    data: Any = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("original evidence-series artifact must be a JSON object")
    return data, raw


def original_retained_ceqanet_series_audit(
    database: Path | None,
    original_execution_path: Path | None,
    policy_path: Path | None,
    manifest_path: Path | None,
) -> dict[str, Any]:
    """Verify actual original source, policy and each series observation offline."""
    if any(path is None for path in (
        database, original_execution_path, policy_path, manifest_path,
    )):
        return {
            "schema_version": _SCHEMA,
            "configured": False,
            "available": False,
            "read_only": True,
            "network_executed": False,
            "series_advanced": False,
            "reason": (
                "Select --operator-database, --operator-ceqanet-csv-evidence, "
                "--operator-ceqanet-csv-access-policy and "
                "--operator-ceqanet-csv-series-manifest at launch."
            ),
        }
    assert database is not None
    assert original_execution_path is not None
    assert policy_path is not None
    assert manifest_path is not None

    policy_audit = original_retained_ceqanet_policy_audit(
        database, original_execution_path, policy_path,
    )
    if policy_audit["original_policy_verification"]["passed"] is not True:
        raise ValueError("original CEQAnet policy failed current source verification")

    manifest, manifest_raw = _json_artifact(
        manifest_path, limit=_MAX_MANIFEST_BYTES,
    )
    if (
        set(manifest) != {"schema_version", "series_file", "evidence_executions"}
        or manifest["schema_version"] != _MANIFEST_VERSION
        or not isinstance(manifest["evidence_executions"], list)
        or len(manifest["evidence_executions"]) > _MAX_SERIES_EXECUTIONS
    ):
        raise ValueError("invalid original CEQAnet evidence-series manifest")
    root = manifest_path.parent
    series_path = _relative_artifact(root, manifest["series_file"])
    series_payload, series_raw = _json_artifact(series_path)
    series = CeqanetCsvEvidenceSeries.model_validate(series_payload)
    series.assert_integrity()

    evidence: list[EvidenceExecutionInput] = []
    retained: list[tuple[Path, str]] = []
    seen_paths: set[str] = {manifest["series_file"]}
    seen_refs: set[str] = set()
    total_bytes = 0
    for entry in manifest["evidence_executions"]:
        if not isinstance(entry, dict) or set(entry) != {"artifact_ref", "file"}:
            raise ValueError("invalid original evidence execution reference")
        artifact_ref = entry["artifact_ref"]
        file_name = entry["file"]
        runtime_artifact_parts(artifact_ref)
        path = _relative_artifact(root, file_name)
        if file_name in seen_paths or artifact_ref in seen_refs:
            raise ValueError("duplicate original evidence execution reference or file")
        seen_paths.add(file_name)
        seen_refs.add(artifact_ref)
        payload, raw = _json_artifact(path)
        total_bytes += len(raw)
        if total_bytes > _MAX_TOTAL_EXECUTION_BYTES:
            raise ValueError("original evidence series exceeds aggregate retention limit")
        execution = CeqanetCsvEvidenceExecution.model_validate(payload)
        execution.assert_integrity()
        evidence.append((artifact_ref, execution))
        retained.append((path, hashlib.sha256(raw).hexdigest()))

    execution_payload, source_raw = _json_artifact(original_execution_path)
    policy_payload, policy_raw = _json_artifact(policy_path)
    if (
        hashlib.sha256(source_raw).hexdigest()
        != policy_audit["retained_execution_sha256"]
        or hashlib.sha256(policy_raw).hexdigest()
        != policy_audit["retained_policy_sha256"]
    ):
        raise ValueError("original policy input changed during series audit")
    original_execution = CeqanetCsvLiveExecution.model_validate(execution_payload)
    original_execution.assert_integrity()
    policy = CeqanetCsvAccessPolicy.model_validate(policy_payload)
    policy.assert_integrity()
    replay = build_ceqanet_csv_encoding_replay(
        original_execution, max_retained_rows=1_000,
    )
    replay_verification = verify_ceqanet_csv_encoding_replay(original_execution, replay)
    if not replay_verification.passed:
        raise ValueError("original evidence series requires passing CSV replay")
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            sources = SourceRegistryStore(session).list_sources()
            registry_digest = source_registry_digest(sources)
            if registry_digest != policy_audit["registry_digest"]:
                raise ValueError("original source registry changed during series audit")
        maturity = build_ceqanet_source_maturity_proposal(
            sources, original_execution, replay, replay_verification,
        )
        maturity_verification = verify_ceqanet_source_maturity_proposal(
            sources, original_execution, replay, replay_verification, maturity,
        )
        policy_verification = verify_ceqanet_csv_access_policy(
            sources, original_execution, replay, replay_verification, maturity,
            maturity_verification, policy,
        )
        if not policy_verification.passed:
            raise ValueError("original evidence-series policy verification failed")
        series_verification = verify_ceqanet_csv_evidence_series(
            sources,
            original_execution,
            replay,
            replay_verification,
            maturity,
            maturity_verification,
            policy,
            policy_verification,
            evidence,
            series,
        )
        if not series_verification.passed:
            raise ValueError(
                "original CEQAnet evidence-series verification failed: "
                + "; ".join(series_verification.findings)
            )
        # Revalidate every on-disk input and the current authoritative registry.
        # Only SHA-256 digests survive this check; full response bytes stay private.
        for path, digest in (
            (manifest_path, hashlib.sha256(manifest_raw).hexdigest()),
            (series_path, hashlib.sha256(series_raw).hexdigest()),
            *retained,
            (original_execution_path, hashlib.sha256(source_raw).hexdigest()),
            (policy_path, hashlib.sha256(policy_raw).hexdigest()),
        ):
            if hashlib.sha256(
                read_runtime_artifact(path, max_bytes=_MAX_JSON_BYTES)
            ).hexdigest() != digest:
                raise ValueError("original retained evidence changed during series audit")
        with Session(engine, autoflush=False) as session:
            if source_registry_digest(
                SourceRegistryStore(session).list_sources()
            ) != registry_digest:
                raise ValueError("original source registry changed during series audit")
    finally:
        engine.dispose()

    return {
        "schema_version": _SCHEMA,
        "available": True,
        "configured": True,
        "original_policy_digest": policy.policy_digest,
        "original_registry_digest": registry_digest,
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        "series_artifact_sha256": hashlib.sha256(series_raw).hexdigest(),
        "original_series_verification": series_verification.model_dump(mode="json"),
        "series": series.model_dump(mode="json"),
        "retained_execution_count": len(evidence),
        "retained_execution_sha256": [digest for _path, digest in retained],
        "policy_date_window_state": policy_audit["date_window_state"],
        "read_only": True,
        "network_executed": False,
        "persistence_mutated": False,
        "series_advanced": False,
        "source_promotion_authorized": False,
        "production_recurring_execution_authorized": False,
        "access_to_remote_source_confirmed": False,
        "commercial_authority_granted": False,
        "meaning": (
            "An independently verified historical evidence series is not a new "
            "collection authorization, source promotion, scheduler, or proof of "
            "present permission. Existing explicit live execution remains "
            "separately authorized through the original policy-bound service."
        ),
    }
