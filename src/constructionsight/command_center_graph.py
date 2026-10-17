"""Bounded read-only views of the existing durable intelligence graph and event journal."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from constructionsight.intelligence.relationship_query_service import canonical_investigation_id
from constructionsight.storage.database import (
    ensure_database_transaction,
    managed_session,
    prepare_private_database,
    session_factory,
)
from constructionsight.storage.intelligence_orm import (
    IntelligenceProjectClusterRecord,
    IntelligenceRuntimeEventRecord,
)
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.operator_read_store import create_operator_read_engine

_NODE_LIMIT = 250
_EDGE_LIMIT = 500
_INACTIVE = {"rejected", "stale", "superseded"}


def _node(store: IntelligenceStore, identity: str) -> dict[str, Any] | None:
    project = store.get_project_cluster(identity)
    if project is not None:
        return {
            "id": identity,
            "kind": "investigation",
            "label": project.project_name or identity,
            "status": project.cluster_status.value,
            "evidence_ids": project.evidence_record_ids[:50],
            "evidence_truncated": len(project.evidence_record_ids) > 50,
            "canonical_id": canonical_investigation_id(store, identity),
            "identity_verified": False,
        }
    entity = store.get_entity(identity)
    if entity is not None:
        return {
            "id": identity,
            "kind": entity.entity_type.value,
            "label": entity.canonical_name,
            "status": entity.identity_status.value,
            "evidence_ids": entity.evidence_record_ids[:50],
            "evidence_truncated": len(entity.evidence_record_ids) > 50,
            "source_names": entity.source_names,
            "identity_verified": False,
        }
    evidence = store.get_evidence(identity)
    if evidence is not None:
        return {
            "id": identity,
            "kind": "evidence",
            "label": evidence.source_name,
            "status": "retained_artifact",
            "evidence_ids": [identity],
            "content_hash": evidence.content_hash,
            "source_family": evidence.source_family,
            "limitations": evidence.limitations,
            "identity_verified": False,
        }
    return None


def _snapshot(store: IntelligenceStore, root: str | None, depth: int) -> dict[str, Any]:
    cursor = store.runtime_event_cursor()
    roots_truncated = False
    if root:
        if _node(store, root) is None:
            raise ValueError("unknown graph root")
        roots = [root]
    else:
        ids = list(
            store.session.scalars(
                select(IntelligenceProjectClusterRecord.project_cluster_id)
                .order_by(IntelligenceProjectClusterRecord.project_cluster_id)
                .limit(26)
            )
        )
        roots_truncated = len(ids) > 25
        roots = sorted({canonical_investigation_id(store, item) for item in ids[:25]})
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}
    truncated = roots_truncated
    frontier = list(roots)
    visited: set[str] = set()
    for _level in range(depth):
        following = []
        for identity in frontier:
            if identity in visited:
                continue
            visited.add(identity)
            node = _node(store, identity)
            if node is None:
                continue
            if identity not in nodes and len(nodes) >= _NODE_LIMIT:
                truncated = True
                break
            nodes[identity] = node
            relationships = store.list_relationships_for_target(identity, limit=101)
            truncated = truncated or len(relationships) > 100
            for relation in relationships[:100]:
                if relation.relationship_status.value in _INACTIVE:
                    continue
                if len(edges) >= _EDGE_LIMIT:
                    truncated = True
                    break
                endpoints = [relation.subject_entity_id, relation.object_entity_id]
                missing = [target for target in endpoints if target not in nodes]
                if len(nodes) + len(missing) > _NODE_LIMIT:
                    truncated = True
                    continue
                resolved = {target: _node(store, target) for target in missing}
                if any(value is None for value in resolved.values()):
                    raise ValueError("persisted graph relationship has a missing endpoint")
                for target, value in resolved.items():
                    if value is not None:
                        nodes[target] = value
                edges[relation.relationship_id] = {
                    "id": relation.relationship_id,
                    "source": relation.subject_entity_id,
                    "target": relation.object_entity_id,
                    "kind": "relationship",
                    "predicate": relation.predicate,
                    "status": relation.relationship_status.value,
                    "confidence": relation.confidence_score,
                    "supporting_evidence_ids": relation.supporting_evidence_ids[:50],
                    "evidence_truncated": len(relation.supporting_evidence_ids) > 50
                    or len(relation.contradictory_evidence_ids) > 50,
                    "contradictory_evidence_ids": relation.contradictory_evidence_ids[:50],
                    "summary": relation.evidence_summary,
                    "identity_verified": False,
                }
                following.extend(endpoints)
        frontier = list(dict.fromkeys(following))
    # These edges display exact retained evidence references, not inferred relationships.
    for node in list(nodes.values()):
        if node["kind"] == "evidence":
            continue
        for evidence_id in node["evidence_ids"]:
            if len(edges) >= _EDGE_LIMIT or (
                evidence_id not in nodes and len(nodes) >= _NODE_LIMIT
            ):
                truncated = True
                break
            evidence_node = _node(store, evidence_id)
            if evidence_node is None:
                raise ValueError("graph node references missing retained evidence")
            nodes[evidence_id] = evidence_node
            identity = hashlib.sha256((node["id"] + "\0" + evidence_id).encode()).hexdigest()
            edges["retained-reference:" + identity] = {
                "id": "retained-reference:" + identity,
                "source": node["id"],
                "target": evidence_id,
                "kind": "retained_reference",
                "predicate": "retained_evidence_reference",
                "status": "retained_reference",
                "supporting_evidence_ids": [evidence_id],
                "contradictory_evidence_ids": [],
                "identity_verified": False,
            }
    return {
        "available": True,
        "schema_version": "constructionsight.live-graph/v1",
        "cursor": cursor,
        "anchor": store.latest_runtime_event_id(),
        "roots": roots,
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "truncated": truncated,
        "depth": depth,
        "limits": {"nodes": _NODE_LIMIT, "edges": _EDGE_LIMIT, "roots": 25},
        "commercial_authority_granted": False,
    }


def graph_view(
    directory: Path,
    *,
    mode: str = "snapshot",
    root: str | None = None,
    depth: int = 1,
    after: int = 0,
    anchor: str | None = None,
    evidence_id: str | None = None,
) -> dict[str, Any]:
    """Read committed snapshots/events with bounded work and restart-safe sequence anchors."""
    if mode not in {"snapshot", "events", "evidence"}:
        raise ValueError("unknown graph operation")
    if type(depth) is not int or not 1 <= depth <= 3:
        raise ValueError("graph depth must be between one and three")
    if type(after) is not int or not 0 <= after <= 2**63 - 1:
        raise ValueError("event cursor must fit a nonnegative SQLite sequence")
    if any(
        value is not None and (not value or len(value) > 255)
        for value in (root, anchor, evidence_id)
    ):
        raise ValueError("invalid graph identifier")
    database = directory / "investigations.sqlite3"
    if not database.exists() and not database.is_symlink():
        return {"available": False, "nodes": [], "edges": [], "events": [], "cursor": 0}
    prepare_private_database(database, create=False)
    engine = create_operator_read_engine(database)
    try:
        with managed_session(session_factory(engine)) as session:
            ensure_database_transaction(session)
            store = IntelligenceStore(session)
            if mode == "snapshot":
                return _snapshot(store, root, depth)
            if mode == "evidence":
                if evidence_id is None:
                    raise ValueError("evidence ID required")
                evidence = store.get_evidence(evidence_id)
                if evidence is None:
                    raise ValueError("unknown retained evidence")
                return {"available": True, "evidence": evidence.model_dump(mode="json")}
            tip = store.runtime_event_cursor()
            recorded_anchor = (
                session.scalar(
                    select(IntelligenceRuntimeEventRecord.event_id).where(
                        IntelligenceRuntimeEventRecord.id == after
                    )
                )
                if after
                else None
            )
            if after > tip or (after and anchor != recorded_anchor):
                return {
                    "available": True,
                    "reset_required": True,
                    "events": [],
                    "cursor": tip,
                    "anchor": store.latest_runtime_event_id(),
                }
            page = store.runtime_event_page(after=after, limit=251)
            visible = page[:250]
            next_cursor = visible[-1][0] if visible else after
            next_anchor = visible[-1][1].event_id if visible else recorded_anchor
            return {
                "available": True,
                "reset_required": False,
                "tip": tip,
                "cursor": next_cursor,
                "anchor": next_anchor,
                "has_more": len(page) > 250,
                "events": [
                    {
                        "sequence": sequence,
                        "event_id": event.event_id,
                        "event_type": event.event_type.value,
                        "created_at": event.created_at.isoformat(),
                        "source_service": event.source_service,
                        "message": event.message[:1000],
                        "entity_refs": event.entity_refs[:50],
                        "project_cluster_refs": event.project_cluster_refs[:50],
                        "source_record_refs": event.source_record_refs[:50],
                        "references_truncated": any(
                            len(items) > 50
                            for items in (
                                event.entity_refs,
                                event.project_cluster_refs,
                                event.source_record_refs,
                            )
                        ),
                    }
                    for sequence, event in visible
                ],
            }
    except SQLAlchemyError as exc:
        raise ValueError("graph store query failed") from exc
    finally:
        engine.dispose()
