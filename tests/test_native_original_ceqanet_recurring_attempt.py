"""Manual original recurring attempt requires matching evidence and operator consent."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from constructionsight.ceqanet_recurring_run_service import execute_ceqanet_recurring_run
from constructionsight.command_center_ceqanet_recurring_attempt import (
    execute_reviewed_original_ceqanet_recurring_attempt,
    preview_original_ceqanet_recurring_attempt,
)
from constructionsight.live_command_center import make_server
from tests.test_ceqanet_recurring_run import _install_transport, _ready_checklist
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_native_original_ceqanet_recurring_audit import _original

_ALLOW = {
    "requires_login": False,
    "has_captcha": False,
    "robots_disallows_collection": False,
    "terms_disallow_collection": False,
    "paywalled": False,
    "access_fact_basis": "review:" + "a" * 64,
}


def _selection(*, allowed: bool = True) -> dict[str, object]:
    review = _ALLOW if allowed else {**_ALLOW, "requires_login": None}
    return {"attempt_sequence": 1, "access_review": review}


def test_recurring_attempt_denies_missing_or_unknown_access(tmp_path: Path) -> None:
    db, checklist, definition, manifest, _ = _original(tmp_path)
    unavailable = preview_original_ceqanet_recurring_attempt(
        db, checklist, definition, None, _selection(),
    )
    assert unavailable["may_request_approval"] is False
    denied = preview_original_ceqanet_recurring_attempt(
        db, checklist, definition, manifest, _selection(allowed=False),
    )
    assert denied["may_request_approval"] is False
    assert denied["blockers"]
    assert denied["network_executed"] is False
    with pytest.raises(ValueError):
        execute_reviewed_original_ceqanet_recurring_attempt(
            db, checklist, definition, manifest, {
                **_selection(allowed=False),
                "expected_preview_digest": denied["expected_preview_digest"],
                "review_reason": "Exact source permission not established",
                "caller_confirmation": True,
            },
        )


def test_original_recurring_attempt_one_shot_preserves_source_and_retains_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    db, checklist, definition, manifest, folder = _original(tmp_path)
    preview = preview_original_ceqanet_recurring_attempt(
        db, checklist, definition, manifest, _selection(),
    )
    assert preview["may_request_approval"] is True
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    from constructionsight.ceqanet_recurring_run_models import (
        CeqanetRecurringRunDefinition,
        CeqanetRecurringRunManifest,
    )
    original_definition = CeqanetRecurringRunDefinition.model_validate(
        json.loads(definition.read_text())
    )
    original_manifest = CeqanetRecurringRunManifest.model_validate(
        json.loads(manifest.read_text())
    )
    from constructionsight.storage.database import (
        create_database_engine,
        managed_session,
        session_factory,
    )
    from constructionsight.storage.source_registry import SourceRegistryStore
    engine = create_database_engine(f"sqlite:///{db}")
    with managed_session(session_factory(engine)) as session:
        sources = SourceRegistryStore(session).list_sources()
    engine.dispose()
    transport = _install_transport(monkeypatch)
    original_execution = execute_ceqanet_recurring_run(
        original_definition, original_manifest, sources, _ready_checklist(),
        attempt_sequence=1, execute_live=True,
    )
    assert len(transport.urls) == 2
    input_payload = {
        **_selection(),
        "expected_preview_digest": preview["expected_preview_digest"],
        "review_reason": "Explicit exact approved manual source attempt",
        "caller_confirmation": True,
    }
    with pytest.raises(ValueError, match="stale"):
        execute_reviewed_original_ceqanet_recurring_attempt(
            db, checklist, definition, manifest, {
                **input_payload, "expected_preview_digest": "0" * 64,
            },
        )
    with patch(
        "constructionsight.command_center_ceqanet_recurring_attempt."
        "execute_authorized_ceqanet_recurring_run",
        return_value=SimpleNamespace(execution=original_execution),
    ) as authorized:
        receipt = execute_reviewed_original_ceqanet_recurring_attempt(
            db, checklist, definition, manifest, input_payload,
        )
    assert authorized.call_count == 1
    assert authorized.call_args.kwargs["caller_confirmation"] is True
    assert receipt["original_verification"]["passed"] is True
    assert receipt["retained_evidence_written"] is True
    assert receipt["schedule_activated"] is False
    assert "snapshots" not in json.dumps(receipt)
    retained = folder / receipt["retained_output_file"]
    assert retained.is_file()
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == receipt[
        "retained_output_sha256"
    ]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert preview_original_ceqanet_recurring_attempt(
        db, checklist, definition, manifest, _selection(),
    )["may_request_approval"] is False


def test_original_recurring_exact_http_preview_and_denied_post(
    tmp_path: Path,
) -> None:
    db, checklist, definition, manifest, folder = _original(tmp_path)
    server = make_server(
        snapshot(), 0, folder,
        operator_database=db,
        operator_ceqanet_recurring_checklist=checklist,
        operator_ceqanet_recurring_definition=definition,
        operator_ceqanet_recurring_manifest=manifest,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            cross = client.post(
                "/api/source-ceqanet-recurring-attempt-preview",
                json=_selection(), headers={"Origin": "https://evil.invalid"},
            )
            assert cross.status_code == 403
            ok = client.post(
                "/api/source-ceqanet-recurring-attempt-preview",
                json=_selection(allowed=False), headers={"Origin": host},
            )
            assert ok.status_code == 200, ok.text
            assert ok.json()["may_request_approval"] is False
            assert client.post(
                "/api/source-ceqanet-recurring-attempt", json={
                    **_selection(),
                    "expected_preview_digest": "0" * 64,
                    "review_reason": "Exact reviewed current source access reason",
                    "caller_confirmation": False,
                },
                headers={"Origin": host},
            ).status_code == 400
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
