"""Native CEQAnet listing/CSV review is a no-network, exact original-service gate."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from constructionsight.adapters.ceqanet_listing_dry_run import CeqanetListingDryRunExecutor
from constructionsight.ceqanet_listing_plan_cli import _dry_run_to_dict, _plan_to_dict
from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot

_FLAGS = ("requires_login", "has_captcha", "robots_disallows_collection",
          "terms_disallow_collection", "paywalled")


def _review(allowed: bool) -> dict[str, object]:
    return {
        **{name: False if allowed else None for name in _FLAGS},
        "access_fact_basis": "review:" + "c" * 64 if allowed else None,
    }


def _request(kind: str, allowed: bool) -> dict[str, object]:
    review = _review(allowed)
    if kind == "csv":
        return {
            "export": {"sch_number": "2026012345", "document_id": None},
            "access_review": review,
        }
    return {
        "query": {
            "counties": ["Riverside", "San Bernardino"],
            "document_types": [], "lead_agencies": [],
            "received_from": None, "received_to": None,
            "posted_from": None, "posted_to": None,
            "high_signal_only": False, "page_size": 25, "max_pages": 2,
        },
        "access_review": review,
    }


@pytest.mark.parametrize("kind", ("listing", "csv"))
def test_native_exact_original_acquisition_does_not_bypass_access(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_listing(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {"metadata": {"synthetic": True}, "snapshots": []}

    def fake_csv(**kwargs: object) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(
            execution=SimpleNamespace(model_dump=lambda **_kw: {
                "request": kwargs["request"].model_dump(mode="json"),
                "execution_digest": "b" * 64,
                "status_code": 200,
            }),
            verification=SimpleNamespace(model_dump=lambda **_kw: {
                "passed": True, "finding_count": 0, "findings": [],
            }),
            authorization=SimpleNamespace(to_dict=lambda: {
                "decision_id": "synthetic-original-authority",
            }),
        )

    monkeypatch.setattr(
        "constructionsight.command_center_ceqanet_acquisition."
        + ("execute_authorized_ceqanet_listing" if kind == "listing"
           else "execute_authorized_ceqanet_csv"),
        fake_listing if kind == "listing" else fake_csv,
    )
    server = make_server(snapshot(), 0, tmp_path / "private")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        headers = {"Origin": host}
        route = f"/api/source-ceqanet-{kind}"
        with httpx.Client(base_url=host, trust_env=False) as client:
            unknown = _request(kind, False)
            denied = client.post(route + "-preview", json=unknown, headers=headers)
            assert denied.status_code == 200, denied.text
            assert denied.json()["may_request_approval"] is False
            assert denied.json()["network_executed"] is False
            assert calls == []
            assert client.post(route + "-preview", json=unknown).status_code == 403

            request = _request(kind, True)
            response = client.post(route + "-preview", json=request, headers=headers)
            assert response.status_code == 200, response.text
            preview = response.json()
            assert preview["may_request_approval"] is True
            if kind == "listing":
                assert preview["policy_id"] == "CS-NET-002"
                assert preview["request_count"] == 2
                assert preview["original_dry_run"]["metadata"]["executed_request_count"] == 0
                assert preview["original_dry_run"]["metadata"]["downloads_documents"] is False
            else:
                assert preview["policy_id"] == "CS-NET-003"
                assert preview["original_request"]["source_url"] == (
                    "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026012345"
                )
                assert preview["original_request"]["network_authorized"] is False
            approved = {
                **request,
                "expected_preview_digest": preview["expected_preview_digest"],
                "review_reason": (
                    "Authorize exactly this reviewed bounded synthetic public request."
                ),
                "caller_confirmation": True,
            }
            assert client.post(route, json=approved).status_code == 403
            assert client.post(
                route, json=approved, headers={"Origin": "https://foreign.invalid"},
            ).status_code == 403
            assert client.post(
                route + "?extra=1", json=approved, headers=headers,
            ).status_code == 400
            for changed in (
                {**approved, "caller_confirmation": False},
                {**approved, "review_reason": "short"},
                {**approved, "expected_preview_digest": "f" * 64},
                {**approved, "unknown": 1},
                {**approved, "access_review": {
                    **request["access_review"], "has_captcha": True,
                }},
                {**approved, "access_review": {
                    **request["access_review"], "requires_login": None,
                }},
                {**approved, "access_review": {
                    **request["access_review"], "access_fact_basis": None,
                }},
            ):
                rejected = client.post(route, json=changed, headers=headers)
                assert rejected.status_code == 400, rejected.text
            assert calls == []
            accepted = client.post(route, json=approved, headers=headers)
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["commercial_authority_granted"] is False
            assert len(calls) == 1
            assert calls[0]["caller_confirmation"] is True
            assert calls[0]["access_profile"].access_fact_basis == "review:" + "c" * 64
            if kind == "listing":
                plan = calls[0]["plan"]
                assert calls[0]["max_response_bytes"] == 50_000
                assert preview["original_plan"] == _plan_to_dict(plan)
                assert preview["original_dry_run"] == _dry_run_to_dict(
                    CeqanetListingDryRunExecutor().run(plan), plan,
                )
            else:
                assert calls[0]["max_body_bytes"] == 10_000_000
                assert calls[0]["max_retained_rows"] == 1_000
                assert accepted.json()["original_verification"]["passed"] is True
                assert accepted.json()["persistence_mutated"] is False
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_original_acquisition_refuses_unbounded_filters_and_invalid_identity() -> None:
    from constructionsight.command_center_ceqanet_acquisition import (
        preview_original_ceqanet_csv,
        preview_original_ceqanet_listing,
    )

    for changes in (
        {"counties": [], "document_types": [], "lead_agencies": []},
        {"page_size": True},
        {"page_size": 101},
        {"max_pages": 11},
        {"text_terms": ["unverified text search"]},
        {"counties": ["Riverside\nInjected"]},
        {"counties": ["Riverside"] * 16},
        {"received_from": "2026-02-30"},
    ):
        request = _request("listing", True)
        with pytest.raises(ValueError):
            preview_original_ceqanet_listing({
                **request, "query": {**request["query"], **changes},
            })
    for export in (
        {"sch_number": "202601234", "document_id": None},
        {"sch_number": "2026012345", "document_id": True},
        {"sch_number": "2026012345", "document_id": -1},
        {"sch_number": "2026012345", "document_id": None, "unexpected": 1},
    ):
        request = _request("csv", True)
        with pytest.raises(ValueError):
            preview_original_ceqanet_csv({**request, "export": export})
