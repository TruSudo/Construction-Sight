"""Original source attribution and read contracts survive the native handoff."""

from __future__ import annotations

import hashlib
import json
from contextlib import ExitStack
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from constructionsight import live_command_center as native
from constructionsight.operator_source_aliases import load_source_attribution_aliases
from constructionsight.operator_web import create_handler
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.domain_store import CeqaStore, PermitStore
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_dashboard import _record
from tests.test_operator_source_aliases import _payload
from tests.test_operator_source_registry import _source


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    database = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{database}")
    initialize_database(engine)
    record = _record()
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(_source("Canonical public source"))
        CeqaStore(session).upsert(record)
        PermitStore(session).upsert(PermitRecord(
            permit_key="fixture:permit", permit_number="Synthetic permit",
            jurisdiction="Synthetic agency", county="San Bernardino",
            site=record.site, entities=record.entities, provenance=record.provenance,
        ))
    engine.dispose()
    aliases = tmp_path / "retained-aliases.json"
    payload = _payload()
    payload["mappings"][0]["alias_source_name"] = "Synthetic integration fixture"
    aliases.write_text(json.dumps(payload), encoding="utf-8")
    return database, aliases


def _start(stack: ExitStack, server: ThreadingHTTPServer) -> str:
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def close() -> None:
        server.shutdown()
        server.server_close()
        thread.join()

    stack.callback(close)
    return f"http://127.0.0.1:{server.server_port}"


def test_native_original_read_contracts_and_exact_alias_attribution_match(tmp_path: Path) -> None:
    database, aliases = _fixture(tmp_path)
    before = database.read_bytes(), aliases.read_bytes()
    with ExitStack() as stack:
        original_url = _start(stack, ThreadingHTTPServer(
            ("127.0.0.1", 0), create_handler(
                database, source_attribution_aliases_path=aliases,
            ),
        ))
        native_url = _start(stack, native.make_server(
            snapshot(), 0, tmp_path / "native", operator_database=database,
            operator_source_attribution_aliases=aliases,
        ))
        original = stack.enter_context(httpx.Client(base_url=original_url, trust_env=False))
        current = stack.enter_context(httpx.Client(base_url=native_url, trust_env=False))
        routes = (
            ("source-registry", "source-registry", ""),
            ("source-revision", "source-revision", ""),
            ("source-review-queue", "source-review-queue", "kind=all&limit=1&offset=1"),
            ("candidate-preview", "candidate-preview", "kind=ceqa&record_id=fixture:one"),
            ("parcel-candidates", "parcel-candidates", "kind=permit&record_id=fixture:permit"),
            ("watchlist", "source-watchlist", ""),
            ("workflows", "workflows", "limit=25&offset=0"),
            ("workflow-summary", "workflow-summary", ""),
            ("results", "results", "limit=25&offset=0"),
            ("entity-index", "source-entity-index", "kind=all&county=San+Bernardino"),
            ("entity-neighborhood", "source-entity-neighborhood", "entity_key=fixture:party"),
            ("timeline", "source-timeline", "kind=all"),
            ("footprint", "source-footprint", "kind=all"),
            ("capture-queue", "source-capture-queue", ""),
            ("ingestion-inbox", "source-ingestion-inbox", ""),
            ("smarts-status", "source-smarts-status", ""),
        )
        for old, new, query in routes:
            previous = original.get(f"/api/{old}?{query}")
            response = current.get(f"/api/{new}?{query}")
            assert previous.status_code == response.status_code == 200, (old, previous.text,
                                                                         response.text)
            actual = response.json()
            assert actual.pop("available") is True
            assert actual == previous.json(), old
        registry = current.get("/api/source-registry").json()
        assert registry["source_aliases_configured"] is True
        assert registry["source_aliases_applied"] is True
        assert registry["source_alias_mapping_count"] == 1
        assert registry["source_alias_artifact_sha256"] == hashlib.sha256(before[1]).hexdigest()
        assert registry["entries"][0]["attributed_via_alias_records_in_scan"] == 2
        assert registry["verification_metadata_is_authority"] is False
        # Both servers retain the same validated startup snapshot, even if the
        # path is later replaced. Neither silently adopts changed assertions.
        aliases.write_text("{}", encoding="utf-8")
        assert current.get("/api/source-registry").json() == registry
        assert original.get("/api/source-registry").json() == {
            key: value for key, value in registry.items() if key != "available"
        }
    assert database.read_bytes() == before[0]


def test_invalid_alias_configuration_fails_before_native_state_creation(tmp_path: Path) -> None:
    database, aliases = _fixture(tmp_path)
    directory = tmp_path / "native"
    before = database.read_bytes()
    with pytest.raises(ValueError, match="require an existing operator database"):
        native.make_server(snapshot(), 0, directory, operator_source_attribution_aliases=aliases)
    payload = _payload()
    payload["network_executed"] = True
    aliases.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="authority state"):
        native.make_server(snapshot(), 0, directory, operator_database=database,
                           operator_source_attribution_aliases=aliases)
    aliases.write_text("not JSON", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid"):
        native.make_server(snapshot(), 0, directory, operator_database=database,
                           operator_source_attribution_aliases=aliases)
    assert not directory.exists()
    assert database.read_bytes() == before


def test_alias_artifact_retains_original_no_follow_reader(tmp_path: Path) -> None:
    database, aliases = _fixture(tmp_path)
    link = tmp_path / "linked-aliases.json"
    link.symlink_to(aliases)
    with pytest.raises(OSError):
        load_source_attribution_aliases(link)
    with pytest.raises(OSError):
        native.make_server(snapshot(), 0, tmp_path / "native", operator_database=database,
                           operator_source_attribution_aliases=link)


def test_native_cli_passes_exact_original_alias_artifact_without_collection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, aliases = _fixture(tmp_path)
    folder = tmp_path / "native"
    folder.mkdir()
    (folder / "active.json").write_text(json.dumps(snapshot()), encoding="utf-8")
    received: dict[str, Any] = {}

    class Server:
        server_port = 1

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            received["closed"] = True

    def bind(*args: Any, **kwargs: Any) -> Server:
        received.update(kwargs)
        return Server()

    monkeypatch.setattr(native, "make_server", bind)
    assert native.main([
        "--offline", "--no-browser", "--data-dir", str(folder),
        "--operator-database", str(database),
        "--operator-source-attribution-aliases", str(aliases),
    ]) == 0
    assert received["operator_source_attribution_aliases"] == aliases
    assert received["operator_database"] == database
    assert received["closed"] is True
