"""Original CEQAnet policy is audited against current retained original evidence."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from constructionsight.ceqanet_csv_access_policy_models import CeqanetCsvAccessPolicy
from constructionsight.ceqanet_csv_access_policy_service import (
    build_ceqanet_csv_access_policy,
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
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import (
    create_database_engine,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_native_original_ceqanet_maturity import _retained

_ROOT = Path(__file__).resolve().parents[1]


def _configured(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    db, evidence, folder = _retained(tmp_path)
    engine = create_database_engine(f"sqlite:///{db}")
    with managed_session(session_factory(engine)) as session:
        sources = SourceRegistryStore(session).list_sources()
    engine.dispose()
    execution = CeqanetCsvLiveExecution.model_validate(
        json.loads(evidence.read_text(encoding="utf-8"))
    )
    replay = build_ceqanet_csv_encoding_replay(execution, max_retained_rows=1_000)
    replay_verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    maturity = build_ceqanet_source_maturity_proposal(
        sources, execution, replay, replay_verification,
    )
    maturity_verification = verify_ceqanet_source_maturity_proposal(
        sources, execution, replay, replay_verification, maturity,
    )
    today = datetime.now(UTC).date()
    policy = build_ceqanet_csv_access_policy(
        sources, execution, replay, replay_verification, maturity, maturity_verification,
        effective_date=today - timedelta(days=1),
        expires_on=today + timedelta(days=1),
    )
    assert maturity_verification.passed
    policy_path = folder / "existing-policy.json"
    policy_path.write_text(
        json.dumps(policy.model_dump(mode="json")), encoding="utf-8",
    )
    policy_path.chmod(0o600)
    return db, evidence, policy_path, folder


def test_original_policy_native_audit_matches_current_evidence_without_effect(
    tmp_path: Path,
) -> None:
    db, evidence, policy, _folder = _configured(tmp_path)
    before_db = hashlib.sha256(db.read_bytes()).hexdigest()
    original_execution = evidence.read_bytes()
    original_policy = policy.read_bytes()
    value = original_retained_ceqanet_policy_audit(db, evidence, policy)
    assert value["available"] is True
    assert value["original_policy_verification"]["passed"] is True
    assert value["registry_and_source_evidence_verified"] is True
    assert value["date_window_state"] == "date_window_current"
    assert value["original_policy"]["max_requests_per_execution"] == 1
    assert value["original_policy"]["retry_count"] == 0
    assert not any(value[k] for k in (
        "network_executed", "persistence_mutated", "policy_created",
        "policy_activated", "registry_promoted",
        "access_to_remote_source_confirmed", "recurring_collection_authorized",
        "commercial_authority_granted",
    ))
    assert "retained_body_base64" not in json.dumps(value)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before_db
    assert evidence.read_bytes() == original_execution
    assert policy.read_bytes() == original_policy


def test_original_policy_native_audit_rejects_stale_tampered_and_wrong_provenance(
    tmp_path: Path,
) -> None:
    db, evidence, policy, _folder = _configured(tmp_path)
    assert original_retained_ceqanet_policy_audit(None, evidence, policy)[
        "available"
    ] is False
    assert original_retained_ceqanet_policy_audit(db, evidence, None)[
        "available"
    ] is False
    original = json.loads(policy.read_text(encoding="utf-8"))
    policy.write_text(json.dumps({**original, "retry_count": 1}))
    with pytest.raises(ValueError):
        original_retained_ceqanet_policy_audit(db, evidence, policy)
    policy.write_text(json.dumps(original), encoding="utf-8")
    # A valid, digest-bound but time-expired policy remains read-only.
    active = CeqanetCsvAccessPolicy.model_validate(original)
    old = active.model_copy(update={
        "effective_date": active.effective_date - timedelta(days=20),
        "expires_on": active.expires_on - timedelta(days=20),
        "policy_digest": "0" * 64,
    })
    old = old.model_copy(update={"policy_digest": old.computed_digest()})
    policy.write_text(json.dumps(old.model_dump(mode="json")))
    expired = original_retained_ceqanet_policy_audit(db, evidence, policy)
    assert expired["original_policy_verification"]["passed"] is True
    assert expired["date_window_state"] == "expired"
    assert expired["policy_activated"] is False
    policy.write_text(json.dumps(original))
    evidence.write_text(json.dumps({
        **json.loads(evidence.read_text(encoding="utf-8")),
        "error": "tampered",
    }))
    with pytest.raises(ValueError):
        original_retained_ceqanet_policy_audit(db, evidence, policy)


def test_original_policy_native_get_only_and_denied_unconfigured(tmp_path: Path) -> None:
    db, evidence, policy, folder = _configured(tmp_path)
    server = make_server(
        snapshot(), 0, folder,
        operator_database=db,
        operator_ceqanet_csv_evidence=evidence,
        operator_ceqanet_csv_access_policy=policy,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            before = hashlib.sha256(db.read_bytes()).hexdigest()
            result = client.get("/api/source-ceqanet-policy-audit")
            assert result.status_code == 200, result.text
            assert result.json()["original_policy_verification"]["passed"] is True
            assert client.get(
                "/api/source-ceqanet-policy-audit?apply=1"
            ).status_code == 409
            assert client.post(
                "/api/source-ceqanet-policy-audit", json={"activate": True},
                headers={"Origin": host},
            ).status_code == 501
            assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_original_policy_launch_rejects_missing_evidence_and_symlink(
    tmp_path: Path,
) -> None:
    db, evidence, policy, folder = _configured(tmp_path)
    with pytest.raises(ValueError, match="requires retained CSV evidence"):
        make_server(
            snapshot(), 0, folder, operator_database=db,
            operator_ceqanet_csv_access_policy=policy,
        )
    symlink = folder / "linked-policy.json"
    symlink.symlink_to(policy)
    with pytest.raises(ValueError, match="existing regular file"):
        make_server(
            snapshot(), 0, folder, operator_database=db,
            operator_ceqanet_csv_evidence=evidence,
            operator_ceqanet_csv_access_policy=symlink,
        )
