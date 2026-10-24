"""Bounded automatic intake of explicitly placed, retained local source artifacts.

The inbox grants no network or source-review authority. Original inputs remain in
place; the worker retains exact bytes and uses existing source validation services.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path

from constructionsight.intelligence.investigation_service import _identity
from constructionsight.intelligence.schemas import RuntimeEvent, RuntimeEventType
from constructionsight.investigation_runtime import (
    MAX_INPUT_BYTES,
    RUNTIME_SOURCE_KINDS,
    InvestigationRuntime,
)
from constructionsight.storage.database import managed_session
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.runtime_artifacts import (
    anchored_artifact_parent,
    read_runtime_artifact,
    read_runtime_text,
    write_runtime_text,
)


def poll_retained_inbox(runtime: InvestigationRuntime, *, limit: int = 25) -> dict[str, int]:
    """Resume a fair bounded scan; enqueue and retain before advancing its cursor."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("inbox limit must be between 1 and 100")
    cursor_path = runtime.directory / "investigation-inbox-cursor.json"
    cursor = (
        json.loads(read_runtime_text(cursor_path, max_bytes=4096)) if cursor_path.exists() else {}
    )
    if not isinstance(cursor, dict) or set(cursor) - {"after"}:
        raise ValueError("invalid investigation inbox cursor")
    after = cursor.get("after", "")
    if not isinstance(after, str) or len(after) > 1024:
        raise ValueError("invalid investigation inbox cursor")
    paths = []
    for kind in RUNTIME_SOURCE_KINDS:
        folder = runtime.directory / "investigation-inbox" / kind
        if not folder.exists() and not folder.is_symlink():
            continue
        with anchored_artifact_parent(folder / "scan") as (descriptor, _):
            with os.scandir(descriptor) as entries:
                page = list(itertools.islice(entries, 1001))
            if len(page) > 1000:
                raise ValueError("inbox source directory exceeds 1000 entries; split the export")
            for entry in page:
                if Path(entry.name).suffix.lower() == ".json":
                    paths.append((f"{kind}/{entry.name}", kind))
    paths.sort()
    following = [(name, kind) for name, kind in paths if name > after]
    accepted = failed = 0
    for name, kind in following[:limit]:
        path = runtime.directory / "investigation-inbox" / name
        content = None
        try:
            content = read_runtime_artifact(path, max_bytes=MAX_INPUT_BYTES)
            runtime.enqueue_bytes(content, kind)
            accepted += 1
        except (ValueError, OSError):
            failed += 1
            # Deduplicate identical failed observations without exposing their
            # contents or pretending that a failed file became an investigation.
            digest = hashlib.sha256(content).hexdigest() if content is not None else None
            with managed_session(runtime.queue.factory) as session:
                store = IntelligenceStore(session)
                event_id = _identity("event:investigation-inbox-error", [name, digest])
                if store.get_runtime_event(event_id) is not None:
                    continue
                store.add_runtime_event(
                    RuntimeEvent(
                        event_id=event_id,
                        event_type=RuntimeEventType.ENRICHMENT_FAILED,
                        source_service="investigation_retained_inbox",
                        payload={
                            "relative_input": name,
                            "input_sha256": digest,
                            "error_code": "retained_input_validation_failed",
                        },
                        message="Retained inbox input requires review; no source facts published.",
                        requires_user_attention=True,
                    )
                )
    next_after = following[limit - 1][0] if len(following) > limit else ""
    if cursor != {"after": next_after}:
        write_runtime_text(cursor_path, json.dumps({"after": next_after}), max_bytes=4096)
    return {
        "inbox_examined": min(len(following), limit),
        "inbox_accepted": accepted,
        "inbox_failed": failed,
    }
