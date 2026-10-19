"""Reviewed single-original-source HTTP readiness through the original authorized service.

Reuses CS-NET-007's bounded HEAD/405-GET transport and durable allowance.
No scheduled collection, record downloads, registry mutation or source promotion.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_verification_evidence_service import (
    build_authorized_source_verification_evidence_package,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.source_registry import SourceRegistryStore


def _selected_original_source(
    original_database: Path | None, source_name: str, public_url: str,
) -> PublicSource:
    if (
        not isinstance(source_name, str) or not 1 <= len(source_name) <= 255
        or not isinstance(public_url, str) or not 1 <= len(public_url) <= 2048
        or any(ord(char) < 32 or ord(char) == 127 for char in source_name + public_url)
    ):
        raise ValueError("exact original source name and URL required")
    if original_database is None:
        raise ValueError("original operator database is not configured")
    if original_database.is_symlink() or not original_database.is_file():
        raise ValueError("original operator database must be an existing regular file")
    engine = create_operator_read_engine(original_database)
    try:
        with Session(engine, autoflush=False) as session:
            source = SourceRegistryStore(session).get_by_identity(source_name, public_url)
            if source is None:
                raise ValueError("exact original registry source does not exist")
            return source
    finally:
        engine.dispose()


def _source_digest(source: PublicSource) -> str:
    snapshot = json.dumps(
        source.model_dump(mode="json"), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(snapshot).hexdigest()


def preview_exact_original_source_readiness(
    original_database: Path | None, *, source_name: str, public_url: str,
) -> dict[str, Any]:
    """Bind one reviewed check to an unchanged exact original source snapshot."""
    source = _selected_original_source(original_database, source_name, public_url)
    return {
        "schema_version": "constructionsight.original-source-http-review/v1",
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "expected_source_sha256": _source_digest(source),
        "registry_verification_status": source.verification_status.value,
        "network_executed": False,
        "review_required": True,
        "caller_confirmation_required": True,
        "method_sequence": ["HEAD", "GET only on 405"],
        "max_response_bytes": 4096,
        "redirects_followed": False,
        "source_registry_mutated": False,
        "source_promoted": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Manual original CS-NET-007 public reachability check only. HTTP response "
            "does not prove complete or lawful collection, current site identity, "
            "verified source status or permission for outreach/bids."
        ),
    }


def check_reviewed_original_source_readiness(
    original_database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Explicitly authorized exact-source bounded HTTP check; never bulk or automatic."""
    if set(payload) != {
        "source_name", "public_url", "expected_source_sha256",
        "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact original source HTTP review fields required")
    source_name, public_url = payload["source_name"], payload["public_url"]
    expected = payload["expected_source_sha256"]
    reason = payload["review_reason"]
    if (
        not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
        or not isinstance(expected, str) or len(expected) != 64
        or any(char not in "0123456789abcdef" for char in expected)
    ):
        raise ValueError("exact current source receipt and explicit manual review required")
    source = _selected_original_source(original_database, source_name, public_url)
    if _source_digest(source) != expected:
        raise ValueError("original source registry changed; review the exact source again")
    package = build_authorized_source_verification_evidence_package(
        [source], default_adapter_family_specs(),
        caller_confirmation=True, authorization_reason=reason.strip(),
    )
    return {
        "schema_version": "constructionsight.original-source-http-result/v1",
        "source_name": source_name,
        "public_url": public_url,
        "reviewed_source_sha256": expected,
        "original_verification_evidence": package.to_dict(),
        "original_source_registry_mutated": False,
        "source_promoted": False,
        "commercial_authority_granted": False,
        "operator_review_required": True,
        "meaning": (
            "Original bounded one-source reachability evidence only. "
            "Registry verification/authority and source completeness are unchanged."
        ),
    }
