"""Native SMARTS catalog operator access binds one original public metadata read."""

from __future__ import annotations

import threading
from pathlib import Path

import httpx
import pytest

import constructionsight.command_center_smarts_catalog as catalog
import constructionsight.smarts_catalog_probe as probe
from constructionsight.live_command_center import make_server
from tests.test_command_center_investigation_bridge import snapshot


_FACTS = (
    "requires_login",
    "has_captcha",
    "robots_disallows_collection",
    "terms_disallow_collection",
    "paywalled",
)


def _access(allowed: bool) -> dict[str, object]:
    return {
        "access_review": {
            **{key: False if allowed else None for key in _FACTS},
            "access_fact_basis": "review:" + "a" * 64 if allowed else None,
        }
    }


def test_smarts_catalog_native_preview_fails_closed_and_cannot_grant_collection() -> None:
    denied = catalog.preview_original_smarts_catalog(_access(False))
    assert denied["may_request_approval"] is False
    assert denied["access_decision"] == "review_required"
    assert denied["network_executed"] is False
    allowed = catalog.preview_original_smarts_catalog(_access(True))
    assert allowed["may_request_approval"] is True
    assert allowed["request_count"] == 1
    assert allowed["exact_package_id"] == probe.PACKAGE_ID
    assert allowed["expected_resource_ids"] == probe.REQUIRED_RESOURCES
    assert allowed["official_catalog_url"] == probe.CATALOG_ENDPOINT
    assert allowed["maximum_response_bytes"] == 512_000
    assert allowed["collection_authorized"] is False
    assert allowed["expected_review_digest"] == (
        catalog.preview_original_smarts_catalog(_access(True))["expected_review_digest"]
    )
    for invalid in (
        {**_access(True), "other": "unreviewed"},
        {"access_review": {"requires_login": False}},
        {"access_review": {**_access(True)["access_review"], "has_captcha": True}},
        {"access_review": {**_access(True)["access_review"], "paywalled": None}},
        {"access_review": {**_access(True)["access_review"], "access_fact_basis": None}},
        {"access_review": {**_access(True)["access_review"], "access_fact_basis": "foo"}},
    ):
        if invalid["access_review"].get("access_fact_basis") in (None, "foo"):
            if invalid["access_review"].get("access_fact_basis") == "foo":
                with pytest.raises(ValueError):
                    catalog.preview_original_smarts_catalog(invalid)
            else:
                reviewed = catalog.preview_original_smarts_catalog(invalid)
                assert reviewed["may_request_approval"] is False
        elif set(invalid) != {"access_review"} or set(invalid["access_review"]) != (
            set(_FACTS) | {"access_fact_basis"}
        ):
            with pytest.raises(ValueError):
                catalog.preview_original_smarts_catalog(invalid)
        else:
            assert catalog.preview_original_smarts_catalog(invalid)["may_request_approval"] is False


def test_smarts_catalog_native_http_enforces_exact_operator_approval(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    calls: list[str] = []

    def fake_catalog(client: httpx.Client) -> probe.CatalogObservation:
        calls.append("once")
        assert client.follow_redirects is False
        assert client.timeout.connect == 5.0
        return probe.CatalogObservation(
            request_url=(
                probe.CATALOG_ENDPOINT + "?id=" + probe.PACKAGE_ID
            ),
            response_sha256="b" * 64,
            package_modified="2026-10-06T00:00:00",
            resources=tuple(
                {
                    "resource_id": value,
                    "name": name,
                    "format": "CSV",
                    "reported_size_bytes": 50_000,
                    "last_modified": "2026-10-02T00:00:00",
                    "resource_license_metadata": None,
                }
                for name, value in probe.REQUIRED_RESOURCES.items()
            ),
        )

    monkeypatch.setattr(
        "constructionsight.command_center_smarts_catalog.fetch_catalog", fake_catalog
    )
    server = make_server(snapshot(), 0, tmp_path / "private")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        host = f"http://127.0.0.1:{server.server_port}"
        route = "/api/source-smarts-catalog"
        headers = {"Origin": host}
        with httpx.Client(base_url=host, trust_env=False) as client:
            forbidden = client.post(route + "-preview", json=_access(False), headers=headers)
            assert forbidden.status_code == 200, forbidden.text
            assert forbidden.json()["may_request_approval"] is False
            assert calls == []
            preview_response = client.post(
                route + "-preview", json=_access(True), headers=headers
            )
            assert preview_response.status_code == 200, preview_response.text
            digest = preview_response.json()["expected_review_digest"]
            approved = {
                **_access(True),
                "expected_review_digest": digest,
                "review_reason": "Review one official SMARTS public catalog metadata response.",
                "caller_confirmation": True,
            }
            assert client.post(route, json=approved).status_code == 403
            assert client.post(
                route, json=approved, headers={"Origin": "https://foreign.invalid"}
            ).status_code == 403
            assert client.post(
                route + "?ignored=1", json=approved, headers=headers
            ).status_code == 400
            for changed in (
                {**approved, "caller_confirmation": False},
                {**approved, "review_reason": "short"},
                {**approved, "expected_review_digest": "f" * 64},
                {**approved, "unreviewed": 1},
                {**approved, "access_review": {
                    **_access(True)["access_review"], "requires_login": True
                }},
            ):
                denied = client.post(route, json=changed, headers=headers)
                assert denied.status_code == 400, denied.text
            assert calls == []
            result = client.post(route, json=approved, headers=headers)
            assert result.status_code == 200, result.text
            assert len(calls) == 1
            value = result.json()
            assert value["original_catalog_observation"]["package_id"] == (
                probe.PACKAGE_ID
            )
            assert len(value["original_catalog_observation"]["resources"]) == 4
            assert value["original_catalog_observation"]["snapshot_complete"] is False
            assert value["dataset_downloaded"] is False
            assert value["commercial_authority_granted"] is False
            assert value["persistence_mutated"] is False
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_catalog_execute_rejects_stale_access_review_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_client: httpx.Client) -> probe.CatalogObservation:
        raise AssertionError("Denied catalog must never reach transport")

    monkeypatch.setattr(
        "constructionsight.command_center_smarts_catalog.fetch_catalog", forbidden
    )
    preview = catalog.preview_original_smarts_catalog(_access(True))
    approval = {
        **_access(True),
        "expected_review_digest": preview["expected_review_digest"],
        "review_reason": "Request one reviewed public SMARTS CKAN catalog metadata response.",
        "caller_confirmation": True,
    }
    changed = {
        **approval,
        "access_review": {**_access(True)["access_review"], "terms_disallow_collection": True},
    }
    with pytest.raises(ValueError, match="blocked or changed"):
        catalog.execute_reviewed_original_smarts_catalog(changed)
