"""Bounded historical graph projection from committed immutable revision events.

This is a read-only in-memory reconstruction, not a second authority or history database.
Records without a complete retained revision chain are never inferred.
"""

from __future__ import annotations

from typing import Any, cast

from pydantic import BaseModel

from constructionsight.intelligence.schemas import (
    EntityIdentity,
    EvidenceRecord,
    ProjectCluster,
    RelationshipAssertion,
)
from constructionsight.storage.intelligence_store import IntelligenceStore

_HISTORY_EVENT_LIMIT = 12000
_HISTORY_RECORD_LIMIT = 10000
_KINDS = {
    "entity": EntityIdentity,
    "evidence": EvidenceRecord,
    "project_cluster": ProjectCluster,
    "relationship": RelationshipAssertion,
}
_IDS = {
    "entity": "entity_id",
    "evidence": "evidence_id",
    "project_cluster": "project_cluster_id",
    "relationship": "relationship_id",
}


class RetainedGraphHistory:
    """In-memory exact event-sourced graph as of a committed event sequence."""

    def __init__(self, at: int, anchor: str) -> None:
        self.at = at
        self.anchor = anchor
        self.states: dict[str, dict[str, Any]] = {key: {} for key in _KINDS}
        self.revisions = 0
        self.processed_events = 0

    def apply(self, event: Any) -> None:
        self.processed_events += 1
        if self.processed_events > _HISTORY_EVENT_LIMIT:
            raise ValueError("historical graph window exceeds the bounded 12000-event limit")
        if event.source_service != "intelligence_store_revision":
            return
        payload = event.payload
        kind = payload.get("record_kind")
        if kind not in _KINDS:
            return
        identity = payload.get("logical_id")
        previous = payload.get("previous_payload")
        current = payload.get("current_payload")
        if not isinstance(identity, str) or not identity or len(identity) > 255:
            raise ValueError("retained revision has an invalid record identity")
        if not isinstance(current, dict) or (
            previous is not None and not isinstance(previous, dict)
        ):
            raise ValueError("retained graph revision is not complete")
        existing = self.states[kind].get(identity)
        if previous != (existing.model_dump(mode="json") if existing is not None else None):
            raise ValueError("historical graph has a missing or conflicting earlier revision")
        if current.get(_IDS[kind]) != identity:
            raise ValueError("historical graph revision identity does not match its payload")
        model = cast(type[BaseModel], _KINDS[kind]).model_validate(current)
        self.states[kind][identity] = model
        self.revisions += 1
        if sum(len(group) for group in self.states.values()) > _HISTORY_RECORD_LIMIT:
            raise ValueError("historical graph exceeds the bounded 10000-record limit")

    def get_project_cluster(self, identity: str) -> ProjectCluster | None:
        return cast(ProjectCluster | None, self.states["project_cluster"].get(identity))

    def get_entity(self, identity: str) -> EntityIdentity | None:
        return cast(EntityIdentity | None, self.states["entity"].get(identity))

    def get_evidence(self, identity: str) -> EvidenceRecord | None:
        return cast(EvidenceRecord | None, self.states["evidence"].get(identity))

    def list_relationships_for_target(
        self, identity: str, *, limit: int | None = None
    ) -> list[RelationshipAssertion]:
        values = [
            cast(RelationshipAssertion, item)
            for item in self.states["relationship"].values()
            if item.subject_entity_id == identity or item.object_entity_id == identity
        ]
        values.sort(key=lambda value: value.relationship_id)
        return values[:limit] if limit is not None else values

    def runtime_event_cursor(self) -> int:
        return self.at

    def latest_runtime_event_id(self) -> str:
        return self.anchor

    def historical_roots(self) -> list[str]:
        return sorted(self.states["project_cluster"])


def replay_graph_history(store: IntelligenceStore, *, at: int, anchor: str) -> RetainedGraphHistory:
    """Verify the exact event anchor then replay bounded committed before/after revisions."""
    if at < 1:
        raise ValueError("historical graph needs a positive retained event sequence")
    tip = store.runtime_event_cursor()
    if at > tip:
        raise ValueError("historical graph cursor is ahead of the retained journal")
    history = RetainedGraphHistory(at, anchor)
    cursor = 0
    while cursor < at:
        page = store.runtime_event_page(after=cursor, limit=501)
        if not page:
            raise ValueError("historical event sequence has a gap")
        for sequence, event in page:
            if sequence > at:
                break
            history.apply(event)
            cursor = sequence
            if cursor == at and event.event_id != anchor:
                raise ValueError("historical graph event anchor changed; reload the journal")
        if cursor < at and len(page) < 501:
            raise ValueError("historical event sequence is not reachable")
    if history.revisions == 0:
        raise ValueError("no retained graph revisions existed at that history point")
    return history
