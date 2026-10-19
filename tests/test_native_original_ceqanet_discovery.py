"""Native original one-shot CEQAnet discovery remains opt-in and policy bound."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import httpx

from constructionsight.ceqanet_discovery_http import CeqanetDiscoveryResult
from constructionsight.http_transport_models import HttpFailureKind
from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot


def test_ceqanet_native_preview_and_strict_one_shot_authorization(
    monkeypatch, tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_execute_authorized_ceqanet_discovery(
        *, execute_live: bool, authorization_reason: str,
    ) -> SimpleNamespace:
        calls.append({
            "execute_live": execute_live, "authorization_reason": authorization_reason,
        })
        return SimpleNamespace(
            result=CeqanetDiscoveryResult(
                url="https://ceqanet.lci.ca.gov/Search/Advanced",
                reachable=True, status_code=200,
                advanced_search_available=True,
                sch_number_field_detected=True,
                document_type_field_detected=True,
                date_field_detected=True,
                lead_agency_field_detected=True,
                failure_kind=HttpFailureKind.NONE,
                notes="Synthetic bounded public discovery.",
            ),
            authorization=SimpleNamespace(to_dict=lambda: {
                "action": "discover-ceqanet-public-search", "synthetic": True,
            }),
        )

    monkeypatch.setattr(
        "constructionsight.command_center_ceqanet_discovery."
        "ceqanet_discovery_service.execute_authorized_ceqanet_discovery",
        fake_execute_authorized_ceqanet_discovery,
    )
    private = tmp_path / "private"
    server = make_server(snapshot(), 0, private)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            response = client.get("/api/source-ceqanet-discovery-preview")
            assert response.status_code == 200, response.text
            preview = response.json()
            assert preview["policy_id"] == "CS-NET-001"
            assert preview["request_url"] == (
                "https://ceqanet.lci.ca.gov/Search/Advanced"
            )
            assert preview["max_response_bytes"] == 50_000
            assert preview["one_attempt_per_utc_date"] is True
            assert preview["network_executed"] is False
            assert preview["source_registry_mutated"] is False
            assert preview["source_collection_enabled"] is False
            assert client.get(
                "/api/source-ceqanet-discovery-preview?execute_live=true"
            ).status_code == 409
            assert calls == []
            payload = {
                "policy_id": preview["policy_id"],
                "request_url": preview["request_url"],
                "expected_state_digest": preview["expected_state_digest"],
                "utc_date": preview["utc_date"],
                "review_reason": "Approve only this bounded synthetic public discovery.",
                "caller_confirmation": True,
            }
            assert client.post(
                "/api/source-ceqanet-discovery", json=payload,
            ).status_code == 403
            assert client.post(
                "/api/source-ceqanet-discovery", json=payload,
                headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            for candidate in (
                {**payload, "caller_confirmation": False},
                {**payload, "review_reason": "short"},
                {**payload, "policy_id": "CS-NET-999"},
                {**payload, "request_url": "https://example.invalid/Search/Advanced"},
                {**payload, "expected_state_digest": "f" * 64},
                {**payload, "utc_date": "2000-01-01"},
                {**payload, "extra": "live"},
            ):
                rejected = client.post(
                    "/api/source-ceqanet-discovery", json=candidate,
                    headers={"Origin": host},
                )
                assert rejected.status_code == 400, rejected.text
            assert client.post(
                "/api/source-ceqanet-discovery?retry=true",
                json=payload, headers={"Origin": host},
            ).status_code == 400
            assert calls == []
            accepted = client.post(
                "/api/source-ceqanet-discovery", json=payload,
                headers={"Origin": host},
            )
            assert accepted.status_code == 200, accepted.text
            result = accepted.json()
            assert calls == [{
                "execute_live": True,
                "authorization_reason": payload["review_reason"],
            }]
            assert result["original_discovery_result"]["reachable"] is True
            assert result["original_authorization"]["action"] == (
                "discover-ceqanet-public-search"
            )
            assert result["source_registry_mutated"] is False
            assert result["source_collection_enabled"] is False
            assert result["recurring_collection_enabled"] is False
            assert result["commercial_authority_granted"] is False
            assert not (private / "investigations.sqlite3").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
