"""Native CEQAnet recurring manifest review reuses exact historical services."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight.ceqanet_recurring_run_service import (
    build_ceqanet_recurring_run_definition,
    build_ceqanet_recurring_run_manifest,
)
from constructionsight.command_center_ceqanet_recurring_audit import (
    original_retained_ceqanet_recurring_audit,
)
from constructionsight.live_command_center import make_server
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_ceqanet_recurring_run import _ready_checklist, _ready_sources, _template
from tests.test_command_center_investigation_bridge import snapshot


def _original(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    folder = tmp_path / "recurring"
    folder.mkdir(mode=0o700)
    database = folder / "sources.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    original_sources = _ready_sources()
    with managed_session(session_factory(engine)) as session:
        SourceRegistryStore(session).upsert_many(original_sources)
        sources = SourceRegistryStore(session).list_sources()
    engine.dispose()
    checklist = _ready_checklist()
    definition = build_ceqanet_recurring_run_definition(
        sources, checklist,
        source_key="source:ceqanet-state-clearinghouse",
        query_template=_template(),
        timeout_seconds=9.0, max_body_chars=100,
    )
    manifest = build_ceqanet_recurring_run_manifest(
        definition, window_start=__import__("datetime").date(2026, 7, 12),
        window_end=__import__("datetime").date(2026, 7, 14),
    )
    checklist_file = folder / "checklist.json"
    definition_file = folder / "definition.json"
    manifest_file = folder / "manifest.json"
    for path, item in (
        (checklist_file, checklist),
        (definition_file, definition),
        (manifest_file, manifest),
    ):
        path.write_text(json.dumps(item.model_dump(mode="json")), encoding="utf-8")
    return database, checklist_file, definition_file, manifest_file, folder


def test_original_recurring_audit_exact_existing_evidence_no_effect(
    tmp_path: Path,
) -> None:
    database, checklist, definition, manifest, folder = _original(tmp_path)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    files_before = {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in folder.iterdir() if file.is_file()
    }
    review = original_retained_ceqanet_recurring_audit(
        database, checklist, definition, manifest,
    )
    assert review["available"] is True
    assert review["original_definition_verified"] is True
    assert review["original_manifest_verified"] is True
    assert review["ready_for_foreground_attempt"] is True
    assert review["window_start"] == "2026-07-12"
    assert review["window_end"] == "2026-07-14"
    assert review["original_persistence_authorized"] is False
    assert review["original_operator_live_authorization_required"] is True
    assert not any(review[key] for key in (
        "network_executed", "persistence_mutated", "schedule_activated",
        "background_recurring_execution_authorized",
        "manual_execution_performed", "commercial_authority_granted",
    ))
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    assert {
        file.name: hashlib.sha256(file.read_bytes()).hexdigest()
        for file in folder.iterdir() if file.is_file()
    } == files_before


def test_original_recurring_audit_denies_changed_definition_and_checklist(
    tmp_path: Path,
) -> None:
    database, checklist, definition, manifest, _ = _original(tmp_path)
    assert original_retained_ceqanet_recurring_audit(
        None, checklist, definition, manifest,
    )["available"] is False
    original = json.loads(definition.read_text())
    definition.write_text(json.dumps({**original, "max_body_chars": 999}))
    with pytest.raises(ValueError):
        original_retained_ceqanet_recurring_audit(
            database, checklist, definition, manifest,
        )
    definition.write_text(json.dumps(original))
    original_check = json.loads(checklist.read_text())
    checklist.write_text(json.dumps({**original_check, "source_count": 999}))
    with pytest.raises(ValueError):
        original_retained_ceqanet_recurring_audit(
            database, checklist, definition, manifest,
        )


def test_original_recurring_exact_http_get_and_post_denial(tmp_path: Path) -> None:
    database, checklist, definition, manifest, folder = _original(tmp_path)
    server = make_server(
        snapshot(), 0, folder, operator_database=database,
        operator_ceqanet_recurring_checklist=checklist,
        operator_ceqanet_recurring_definition=definition,
        operator_ceqanet_recurring_manifest=manifest,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            response = client.get("/api/source-ceqanet-recurring-audit")
            assert response.status_code == 200, response.text
            assert response.json()["ready_for_foreground_attempt"] is True
            assert client.get(
                "/api/source-ceqanet-recurring-audit?schedule=1"
            ).status_code == 409
            assert client.post(
                "/api/source-ceqanet-recurring-audit", json={"enable": True},
                headers={"Origin": host},
            ).status_code == 501
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_original_recurring_launch_denies_partial_and_symlink_config(
    tmp_path: Path,
) -> None:
    database, checklist, definition, manifest, folder = _original(tmp_path)
    with pytest.raises(ValueError, match="requires all exact retained"):
        make_server(
            snapshot(), 0, folder,
            operator_database=database,
            operator_ceqanet_recurring_manifest=manifest,
        )
    link = folder / "alias.json"
    link.symlink_to(manifest)
    with pytest.raises(ValueError, match="existing regular files"):
        make_server(
            snapshot(), 0, folder,
            operator_database=database,
            operator_ceqanet_recurring_checklist=checklist,
            operator_ceqanet_recurring_definition=definition,
            operator_ceqanet_recurring_manifest=link,
        )
