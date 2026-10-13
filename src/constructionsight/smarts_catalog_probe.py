"""Explicit read-only California SMARTS CKAN catalog metadata probe.

This captures one bounded public metadata response, not a dataset export,
completion watermark, download authorization, or background schedule.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx

from constructionsight.smarts_api import USER_AGENT

CATALOG_ENDPOINT = "https://publish.data.ca.gov/api/3/action/package_show"
PACKAGE_ID = "dd553361-ddc6-4fe6-a95f-c9bf3342e0d1"
MAX_METADATA_BYTES = 512_000
REQUIRED_RESOURCES = {
    "facilities": "8a0ed456-ca69-4b29-9c5b-5de3958dc963",
    "inspections": "33047e47-7d44-46aa-9e0f-1a0f1b0cad66",
    "violations": "9b69a654-0c9a-4865-8d10-38c55b1b8c58",
    "enforcement": "9cf197f4-f1d5-4d43-b94b-ccb155ef14cf",
}


class SmartsCatalogError(ValueError):
    """A resource catalog observation is missing, ambiguous, or invalid."""


@dataclass(frozen=True)
class CatalogObservation:
    request_url: str
    response_sha256: str
    package_modified: str | None
    resources: tuple[dict[str, Any], ...]


def fetch_catalog(client: httpx.Client) -> CatalogObservation:
    """Fetch precisely one fixed, publicly listed package metadata endpoint."""
    try:
        with client.stream(
            "GET", CATALOG_ENDPOINT, params={"id": PACKAGE_ID}, follow_redirects=False
        ) as response:
            if response.status_code != 200:
                raise SmartsCatalogError("Unexpected catalog HTTP status")
            mime = response.headers.get("content-type", "").split(";")[0].strip().lower()
            if mime != "application/json":
                raise SmartsCatalogError("Expected catalog application/json")
            chunks: list[bytes] = []
            count = 0
            for chunk in response.iter_bytes():
                count += len(chunk)
                if count > MAX_METADATA_BYTES:
                    raise SmartsCatalogError("Catalog metadata exceeded byte limit")
                chunks.append(chunk)
            body = b"".join(chunks)
            url = str(response.request.url)
    except httpx.HTTPError as exc:
        raise SmartsCatalogError("Catalog transport failed") from exc
    try:
        parsed = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise SmartsCatalogError("Catalog metadata was not valid JSON") from exc
    if type(parsed) is not dict or parsed.get("success") is not True:
        raise SmartsCatalogError("CKAN did not report a successful catalog observation")
    result = parsed.get("result")
    if type(result) is not dict or result.get("id") != PACKAGE_ID:
        raise SmartsCatalogError("Unexpected SMARTS package identity")
    items = result.get("resources")
    if not isinstance(items, list):
        raise SmartsCatalogError("Catalog resource inventory is missing")
    known: dict[str, dict[str, Any]] = {}
    required = set(REQUIRED_RESOURCES.values())
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise SmartsCatalogError("Malformed resource metadata")
        resource_id = item["id"]
        if resource_id not in required:
            continue
        if resource_id in known:
            raise SmartsCatalogError("Duplicate required resource metadata")
        if str(item.get("format", "")).upper() != "CSV":
            raise SmartsCatalogError("Required public resource is no longer a CSV")
        size = item.get("size")
        if size is not None and (type(size) is not int or size < 0):
            raise SmartsCatalogError("Invalid resource byte-count metadata")
        updated = item.get("last_modified")
        if updated is not None and not isinstance(updated, str):
            raise SmartsCatalogError("Invalid resource modification metadata")
        name = item.get("name")
        if name is not None and not isinstance(name, str):
            raise SmartsCatalogError("Invalid resource title")
        known[resource_id] = {
            "resource_id": resource_id,
            "name": name or "",
            "format": "CSV",
            "reported_size_bytes": size,
            "last_modified": updated,
            "resource_license_metadata": item.get("license_id")
            if isinstance(item.get("license_id"), str) else None,
        }
    if set(known) != required:
        raise SmartsCatalogError("One or more required SMARTS resources are missing")
    modified = result.get("metadata_modified")
    if modified is not None and not isinstance(modified, str):
        raise SmartsCatalogError("Invalid package modification metadata")
    return CatalogObservation(
        request_url=url,
        response_sha256=hashlib.sha256(body).hexdigest(),
        package_modified=modified,
        resources=tuple(known[REQUIRED_RESOURCES[kind]] for kind in REQUIRED_RESOURCES),
    )


def build_catalog_summary(item: CatalogObservation) -> dict[str, Any]:
    return {
        "ok": True,
        "package_id": PACKAGE_ID,
        "source_request_url": item.request_url,
        "source_response_sha256": item.response_sha256,
        "package_last_modified": item.package_modified,
        "resources": [
            {"kind": kind, **resource}
            for kind, resource in zip(REQUIRED_RESOURCES, item.resources, strict=True)
        ],
        "dataset_downloaded": False,
        "snapshot_complete": False,
        "collection_authorized": False,
        "commercial_use_terms_reviewed": False,
        "source_health": "metadata_observation_only",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-call, bounded official SMARTS catalog probe")
    parser.add_argument("--execute-live", action="store_true")
    args = parser.parse_args(argv)
    if not args.execute_live:
        parser.error("Public source access requires explicit --execute-live")
    try:
        with httpx.Client(
            follow_redirects=False,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        ) as client:
            observation = fetch_catalog(client)
        print(json.dumps(build_catalog_summary(observation), indent=2))
    except SmartsCatalogError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
