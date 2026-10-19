"""Native original detail read preserves the original access and consent boundaries."""

from __future__ import annotations

import threading
from pathlib import Path

import httpx

from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot

_URL = "https://ceqanet.lci.ca.gov/Project/Example"
_FLAGS = (
    "requires_login", "has_captcha", "robots_disallows_collection",
    "terms_disallow_collection", "paywalled",
)


def test_native_detail_access_review_and_exact_governed_execution(
    monkeypatch, tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_original_detail(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "metadata": {"policy": "CS-NET-006", "synthetic": True},
            "snapshots": [{"request_url": _URL, "reachable": True}],
        }

    monkeypatch.setattr(
        "constructionsight.command_center_ceqanet_detail."
        "execute_authorized_ceqanet_detail", fake_original_detail,
    )
    server = make_server(snapshot(), 0, tmp_path / "private")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        headers = {"Origin": host}
        review: dict[str, object] = {
            **{key: None for key in _FLAGS}, "access_fact_basis": None,
        }
        with httpx.Client(base_url=host, trust_env=False) as client:
            request = {"detail_url": _URL, "access_review": review}
            denied = client.post(
                "/api/source-ceqanet-detail-preview", json=request, headers=headers,
            )
            assert denied.status_code == 200, denied.text
            assert denied.json()["access_decision"] == "review_required"
            assert denied.json()["may_request_approval"] is False
            assert denied.json()["network_executed"] is False
            assert calls == []
            assert client.post(
                "/api/source-ceqanet-detail-preview", json=request,
            ).status_code == 403
            assert client.post(
                "/api/source-ceqanet-detail-preview?execute=1",
                json=request, headers=headers,
            ).status_code == 400
            blocked = {
                **request,
                "expected_preview_digest": denied.json()["expected_preview_digest"],
                "review_reason": "Perform an explicitly reviewed bounded public read.",
                "caller_confirmation": True,
            }
            assert client.post(
                "/api/source-ceqanet-detail", json=blocked, headers=headers,
            ).status_code == 400
            assert calls == []
            review = {**{key: False for key in _FLAGS},
                      "access_fact_basis": "review:" + "a" * 64}
            request = {"detail_url": _URL, "access_review": review}
            preview_result = client.post(
                "/api/source-ceqanet-detail-preview",
                json=request, headers=headers,
            )
            assert preview_result.status_code == 200, preview_result.text
            preview = preview_result.json()
            assert preview["policy_id"] == "CS-NET-006"
            assert preview["max_response_bytes"] == 50_000
            assert preview["may_request_approval"] is True
            assert preview["source_registry_mutated"] is False
            payload = {
                **request, "expected_preview_digest": preview["expected_preview_digest"],
                "review_reason": "Review one exact synthetic public detail page.",
                "caller_confirmation": True,
            }
            for invalid in (
                {**payload, "expected_preview_digest": "0" * 64},
                {**payload, "caller_confirmation": False},
                {**payload, "review_reason": "short"},
                {**payload, "extra": "unknown"},
                {**payload, "access_review": {
                    **review, "has_captcha": True,
                }},
                {**payload, "access_review": {
                    **review, "terms_disallow_collection": None,
                }},
                {**payload, "access_review": {
                    **review, "access_fact_basis": "not-an-evidence-id",
                }},
                {**payload, "detail_url": "https://example.invalid/Project/Example"},
            ):
                rejected = client.post(
                    "/api/source-ceqanet-detail", json=invalid, headers=headers,
                )
                assert rejected.status_code == 400, rejected.text
            assert client.post(
                "/api/source-ceqanet-detail", json=payload,
                headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            assert calls == []
            approved = client.post(
                "/api/source-ceqanet-detail", json=payload, headers=headers,
            )
            assert approved.status_code == 200, approved.text
            result = approved.json()
            assert result["original_execution"]["metadata"]["synthetic"] is True
            assert result["reviewed_preview_digest"] == preview["expected_preview_digest"]
            assert result["source_registry_mutated"] is False
            assert result["commercial_authority_granted"] is False
            assert len(calls) == 1
            assert calls[0]["detail_url"] == _URL
            assert calls[0]["caller_confirmation"] is True
            assert calls[0]["timeout_seconds"] == 20.0
            assert calls[0]["max_body_bytes"] == 50_000
            assert calls[0]["access_profile"].access_fact_basis == "review:" + "a" * 64
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
