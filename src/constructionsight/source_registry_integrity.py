"""Deterministic source registry integrity helpers."""

from __future__ import annotations

import hashlib
import json

from constructionsight.models import PublicSource


def source_registry_digest(sources: list[PublicSource]) -> str:
    """Return a deterministic SHA-256 digest for registry content and order."""

    payload = [source.model_dump(mode="json") for source in sources]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
