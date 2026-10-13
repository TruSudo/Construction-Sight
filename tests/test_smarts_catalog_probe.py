"""Mocked public SMARTS catalog metadata transport contracts."""

from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from constructionsight.smarts_catalog_probe import (
    CATALOG_ENDPOINT,
    PACKAGE_ID,
    REQUIRED_RESOURCES,
    SmartsCatalogError,
    build_catalog_summary,
    fetch_catalog,
)


def _package() -> dict[str, object]:
    return {
        "success": True,
        "result": {
            "id": PACKAGE_ID,
            "metadata_modified": "2026-10-06T00:00:00",
            "resources": [
                {
                    "id": value,
                    "name": key,
                    "format": "CSV",
                    "size": 50_000,
                    "last_modified": "2026-10-02T00:00:00",
                }
                for key, value in REQUIRED_RESOURCES.items()
            ],
        },
    }


def _fetch(
    payload: dict[str, object], *,
    code: int = 200, mime: str = "application/json",
) -> tuple[dict[str, object], bytes]:
    raw = json.dumps(payload).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(CATALOG_ENDPOINT)
        assert request.url.params["id"] == PACKAGE_ID
        return httpx.Response(code, headers={"content-type": mime}, content=raw)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        observation = fetch_catalog(client)
    return build_catalog_summary(observation), raw


def test_catalog_metadata_fixed_resources_and_independent_sha() -> None:
    report, raw = _fetch(_package())
    assert report["ok"] is True
    assert report["source_response_sha256"] == hashlib.sha256(raw).hexdigest()
    assert [resource["kind"] for resource in report["resources"]] == list(REQUIRED_RESOURCES)
    assert report["dataset_downloaded"] is False
    assert report["source_health"] == "metadata_observation_only"
    assert report["commercial_use_terms_reviewed"] is False


@pytest.mark.parametrize("problem", ["missing", "duplicate", "wrong-format", "wrong-package"])
def test_missing_or_drifted_catalog_fails(problem: str) -> None:
    document = _package()
    result = document["result"]
    assert isinstance(result, dict)
    resources = result["resources"]
    assert isinstance(resources, list)
    if problem == "missing":
        resources.pop()
    elif problem == "duplicate":
        resources.append(dict(resources[0]))
    elif problem == "wrong-format":
        resources[0]["format"] = "HTML"
    else:
        result["id"] = "other"
    with pytest.raises(SmartsCatalogError):
        _fetch(document)


@pytest.mark.parametrize(("code", "mime"), [(302, "application/json"), (200, "text/html")])
def test_invalid_transport_never_accepts_redirects_or_html(code: int, mime: str) -> None:
    raw = json.dumps(_package()).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(code, headers={"content-type": mime}, content=raw)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(SmartsCatalogError):
            fetch_catalog(client)
