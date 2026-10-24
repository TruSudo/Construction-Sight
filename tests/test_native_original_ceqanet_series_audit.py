"""Original retained CEQAnet evidence-series auditor preserves the existing ledger."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import date
from pathlib import Path

import httpx
import pytest

from constructionsight.ceqanet_csv_access_policy_models import CeqanetCsvAccessPolicy
from constructionsight.ceqanet_csv_access_policy_service import (
    verify_ceqanet_csv_access_policy,
)
from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
)
from constructionsight.ceqanet_csv_evidence_series_service import (
    build_ceqanet_csv_evidence_series,
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
from constructionsight.command_center_ceqanet_series_audit import (
    original_retained_ceqanet_series_audit,
)
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import (
    create_database_engine,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_native_original_ceqanet_policy_audit import _configured

_ROOT = Path(__file__).resolve().parents[1]
_ORIGINAL_OBSERVATION = (
    _ROOT / "evidence/source_verification"
    / "ceqanet_csv_evidence_execution_2026-07-14_project.json"
)
_ARTIFACT_REF = (
    "evidence/source_verification/"
    "ceqanet_csv_evidence_execution_2026-07-14_project.json"
)


def _series(tmp_path: Path, *, with_one: bool = False) -> tuple[Path, Path, Path, Path, Path]:
    db, source, policy_path, folder = _configured(tmp_path)
    engine = create_database_engine(f"sqlite:///{db}")
    with managed_session(session_factory(engine)) as session:
        sources = SourceRegistryStore(session).list_sources()
    engine.dispose()
    original = CeqanetCsvLiveExecution.model_validate(
        json.loads(source.read_text(encoding="utf-8"))
    )
    replay = build_ceqanet_csv_encoding_replay(original, max_retained_rows=1_000)
    replay_verification = verify_ceqanet_csv_encoding_replay(original, replay)
    maturity = build_ceqanet_source_maturity_proposal(
        sources, original, replay, replay_verification,
    )
    maturity_verification = verify_ceqanet_source_maturity_proposal(
        sources, original, replay, replay_verification, maturity,
    )
    policy = CeqanetCsvAccessPolicy.model_validate(
        json.loads(policy_path.read_text(encoding="utf-8"))
    )
    if with_one:
        from constructionsight.ceqanet_csv_access_policy_service import (
            build_ceqanet_csv_access_policy,
        )
        policy = build_ceqanet_csv_access_policy(
            sources, original, replay, replay_verification, maturity,
            maturity_verification, effective_date=date(2026, 7, 14),
            expires_on=date(2026, 8, 13),
        )
        policy_path.write_text(json.dumps(policy.model_dump(mode="json")))
    policy_verification = verify_ceqanet_csv_access_policy(
        sources, original, replay, replay_verification, maturity,
        maturity_verification, policy,
    )
    executions = []
    entries = []
    if with_one:
        historical = CeqanetCsvEvidenceExecution.model_validate(
            json.loads(_ORIGINAL_OBSERVATION.read_text(encoding="utf-8"))
        )
        draft = historical.model_copy(update={
            "policy_digest": policy.policy_digest,
            "evidence_execution_digest": "0" * 64,
        })
        valid = draft.model_copy(update={
            "evidence_execution_digest": draft.computed_digest(),
        })
        execution_file = folder / "observation.json"
        execution_file.write_text(json.dumps(valid.model_dump(mode="json")))
        executions.append((_ARTIFACT_REF, valid))
        entries.append({"artifact_ref": _ARTIFACT_REF, "file": "observation.json"})
    series = build_ceqanet_csv_evidence_series(
        sources, original, replay, replay_verification, maturity,
        maturity_verification, policy, policy_verification, executions,
    )
    (folder / "series.json").write_text(
        json.dumps(series.model_dump(mode="json")), encoding="utf-8",
    )
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps({
        "schema_version": "constructionsight.ceqanet_csv_series_manifest.v1",
        "series_file": "series.json",
        "evidence_executions": entries,
    }), encoding="utf-8")
    return db, source, policy_path, manifest, folder


@pytest.mark.parametrize("with_one", [False, True])
def test_original_series_verifies_empty_or_historical_one_without_effect(
    tmp_path: Path, with_one: bool,
) -> None:
    db, source, policy, manifest, folder = _series(tmp_path, with_one=with_one)
    db_before = hashlib.sha256(db.read_bytes()).hexdigest()
    file_before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.iterdir() if p.is_file()
    }
    result = original_retained_ceqanet_series_audit(db, source, policy, manifest)
    assert result["available"] is True
    assert result["original_series_verification"]["passed"] is True
    assert result["series"]["observation_count"] == (1 if with_one else 0)
    assert result["retained_execution_count"] == (1 if with_one else 0)
    assert result["series"]["status"] == "collecting"
    assert result["original_series_verification"]["ready_for_maturity_review"] is False
    assert not any(result[k] for k in (
        "network_executed", "persistence_mutated", "series_advanced",
        "source_promotion_authorized", "production_recurring_execution_authorized",
        "access_to_remote_source_confirmed", "commercial_authority_granted",
    ))
    serialized = json.dumps(result)
    assert "retained_body_base64" not in serialized
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_before
    assert {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.iterdir() if p.is_file()
    } == file_before


def test_native_original_series_unauthorized_and_tampered_inputs(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, folder = _series(tmp_path, with_one=True)
    assert original_retained_ceqanet_series_audit(db, source, policy, None)[
        "available"
    ] is False
    snapshot_raw = json.loads((folder / "series.json").read_text())
    (folder / "series.json").write_text(json.dumps({
        **snapshot_raw, "next_gate": "changed",
    }))
    with pytest.raises(ValueError):
        original_retained_ceqanet_series_audit(db, source, policy, manifest)
    (folder / "series.json").write_text(json.dumps(snapshot_raw))
    original_manifest = json.loads(manifest.read_text())
    manifest.write_text(json.dumps({
        **original_manifest,
        "evidence_executions": [{
            **original_manifest["evidence_executions"][0],
            "file": "../outside.json",
        }],
    }))
    with pytest.raises(ValueError):
        original_retained_ceqanet_series_audit(db, source, policy, manifest)
    manifest.write_text(json.dumps(original_manifest))
    execution = json.loads((folder / "observation.json").read_text())
    (folder / "observation.json").write_text(json.dumps({
        **execution, "policy_digest": "0" * 64,
    }))
    with pytest.raises(ValueError):
        original_retained_ceqanet_series_audit(db, source, policy, manifest)


def test_native_original_series_exact_get_and_post_denied(tmp_path: Path) -> None:
    db, source, policy, manifest, folder = _series(tmp_path)
    server = make_server(
        snapshot(), 0, folder,
        operator_database=db,
        operator_ceqanet_csv_evidence=source,
        operator_ceqanet_csv_access_policy=policy,
        operator_ceqanet_csv_series_manifest=manifest,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            ok = client.get("/api/source-ceqanet-series-audit")
            assert ok.status_code == 200, ok.text
            assert ok.json()["original_series_verification"]["passed"] is True
            assert client.get(
                "/api/source-ceqanet-series-audit?collect=true"
            ).status_code == 409
            assert client.post(
                "/api/source-ceqanet-series-audit", json={"resume": True},
                headers={"Origin": host},
            ).status_code == 501
            assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_original_series_launch_denies_symlinks_and_missing_policy(tmp_path: Path) -> None:
    db, source, policy, manifest, folder = _series(tmp_path)
    with pytest.raises(ValueError, match="requires original policy"):
        make_server(
            snapshot(), 0, folder, operator_database=db,
            operator_ceqanet_csv_evidence=source,
            operator_ceqanet_csv_series_manifest=manifest,
        )
    symlink = folder / "linked-manifest.json"
    symlink.symlink_to(manifest)
    with pytest.raises(ValueError, match="existing regular file"):
        make_server(
            snapshot(), 0, folder, operator_database=db,
            operator_ceqanet_csv_evidence=source,
            operator_ceqanet_csv_access_policy=policy,
            operator_ceqanet_csv_series_manifest=symlink,
        )
