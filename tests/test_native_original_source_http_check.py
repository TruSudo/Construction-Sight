"""Original bounded source HTTP check is reviewed, exact and neither bulk nor automatic."""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import httpx
from sqlalchemy.orm import Session

import constructionsight.source_readiness_service as readiness_service
from constructionsight.live_command_center import make_server
from constructionsight.source_readiness_models import HttpReachabilityResult
from constructionsight.storage.database import create_database_engine, initialize_database
from constructionsight.storage.source_registry import SourceRegistryStore
from tests.test_command_center_investigation_bridge import snapshot
from tests.test_operator_source_registry import _source


def test_native_exact_original_http_readiness_reuses_original_authorization(
    tmp_path: Path, monkeypatch,
) -> None:
    original = tmp_path / "original.sqlite3"
    engine = create_database_engine(f"sqlite:///{original}")
    initialize_database(engine)
    source = _source(
        "Synthetic reviewed HTTP readiness source",
        county="Riverside", public_url="https://ezop.sbcounty.gov/citizenaccess/",
    )
    with Session(engine) as session, session.begin():
        SourceRegistryStore(session).upsert_source(source)
    engine.dispose()
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    checks: list[str] = []

    def local_stub(item):
        checks.append(str(item.public_url))
        return HttpReachabilityResult(
            checked=True, reachable=True, status_code=200,
            method="HEAD", final_url=str(item.public_url),
        )

    # Network is replaced at the original authorized service boundary.
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", local_stub)
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private, operator_database=original)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        params = {"source_name": source.source_name, "public_url": str(source.public_url)}
        with httpx.Client(base_url=base, trust_env=False) as client:
            preview = client.get("/api/source-http-check-preview", params=params)
            assert preview.status_code == 200, preview.text
            received = preview.json()
            assert received["network_executed"] is False
            assert received["review_required"] is True
            assert received["source_promoted"] is False
            assert received["source_url_separately_governed"] is True
            assert received["can_execute_manual_check"] is True
            assert checks == []
            assert client.get("/api/source-http-check-preview", params={
                **params, "extra": "1",
            }).status_code == 409
            assert client.get("/api/source-http-check-preview", params={
                **params, "source_name": "different",
            }).status_code == 409
            assert client.get("/api/source-http-check-preview", params={
                **params, "public_url": "https://example.invalid/different",
            }).status_code == 409
            payload = {
                **params,
                "expected_source_sha256": received["expected_source_sha256"],
                "review_reason": "Review one public synthetic source endpoint, no collection.",
                "caller_confirmation": True,
            }
            assert client.post("/api/source-http-check", json=payload).status_code == 403
            assert client.post(
                "/api/source-http-check", json=payload,
                headers={"Origin": "https://malicious.invalid"},
            ).status_code == 403
            for bad in (
                {**payload, "caller_confirmation": False},
                {**payload, "expected_source_sha256": "0" * 64},
                {**payload, "extra": "network_permission"},
            ):
                assert client.post("/api/source-http-check", json=bad, headers={
                    "Origin": base,
                }).status_code == 400
            assert checks == []
            authorized = client.post(
                "/api/source-http-check", json=payload,
                headers={"Origin": base},
            )
            assert authorized.status_code == 200, authorized.text
            report = authorized.json()
            assert report["reviewed_source_sha256"] == received["expected_source_sha256"]
            evidence = report["original_verification_evidence"]
            assert evidence["source_count"] == 1
            assert evidence["rows"][0]["http_checked"] is True
            assert evidence["rows"][0]["http_status_code"] == 200
            assert report["source_promoted"] is False
            assert report["original_source_registry_mutated"] is False
            assert report["commercial_authority_granted"] is False
            assert checks == [str(source.public_url)]
            assert hashlib.sha256(original.read_bytes()).hexdigest() == before
            assert not (private / "investigations.sqlite3").exists()
            # Existing one-source durable allowance must replay, not recheck.
            repeated = client.post(
                "/api/source-http-check", json=payload, headers={"Origin": base},
            )
            assert repeated.status_code == 200, repeated.text
            assert repeated.json()["original_verification_evidence"] == evidence
            assert checks == [str(source.public_url)]
            # Unauthorized URL cannot consume an allowance or reach the transport
            # even if a caller supplies an exact original source digest.
            from constructionsight.command_center_source_reachability import (
                _source_digest,
            )
            ungoverned = _source("Non-governed synthetic endpoint")
            source_engine = create_database_engine(f"sqlite:///{original}")
            # Explicit database write is fixture setup only, NOT application behavior.
            with Session(source_engine) as source_session, source_session.begin():
                SourceRegistryStore(source_session).upsert_source(ungoverned)
            source_engine.dispose()
            rejected = client.post("/api/source-http-check", json={
                "source_name": ungoverned.source_name,
                "public_url": str(ungoverned.public_url),
                "expected_source_sha256": _source_digest(ungoverned),
                "review_reason": "No network authority granted for this source.",
                "caller_confirmation": True,
            }, headers={"Origin": base})
            assert rejected.status_code == 400
            assert checks == [str(source.public_url)]
            blocked_source = _source(
                "Blocked synthetic retained source",
                public_url="https://ezop.sbcounty.gov/citizenaccess/",
                verification_status="blocked",
            )
            with Session(source_engine) as session, session.begin():
                SourceRegistryStore(session).upsert_source(blocked_source)
            denied_preview = client.get("/api/source-http-check-preview", params={
                "source_name": blocked_source.source_name,
                "public_url": str(blocked_source.public_url),
            })
            assert denied_preview.status_code == 200, denied_preview.text
            assert denied_preview.json()["source_registry_blocked"] is True
            assert denied_preview.json()["can_execute_manual_check"] is False
            blocked_post = client.post("/api/source-http-check", json={
                "source_name": blocked_source.source_name,
                "public_url": str(blocked_source.public_url),
                "expected_source_sha256": _source_digest(blocked_source),
                "review_reason": "Blocked source cannot be checked by this interface.",
                "caller_confirmation": True,
            }, headers={"Origin": base})
            assert blocked_post.status_code == 400
            assert checks == [str(source.public_url)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_unconfigured_source_http_review_is_unavailable_without_side_effects(
    tmp_path: Path,
) -> None:
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with httpx.Client(
            base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
        ) as client:
            response = client.get("/api/source-http-check-preview", params={
                "source_name": "Missing", "public_url": "https://example.invalid/",
            })
            assert response.status_code == 409
            assert not (private / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
