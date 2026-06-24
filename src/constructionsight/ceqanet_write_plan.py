"""CEQAnet write plan preview service.

This module converts CEQAnet persistence preview JSON into deterministic write
plan operations. It does not open databases, execute writes, perform network
requests, or download documents.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

TargetCollection = Literal["ceqa_records", "sites", "entities"]
OperationAction = Literal["upsert_preview"]


@dataclass(frozen=True)
class CeqanetWriteOperation:
    """One non-mutating write operation preview."""

    operation_id: str
    action: OperationAction
    target_collection: TargetCollection
    target_key: str
    source_index: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe operation payload."""

        return {
            "operation_id": self.operation_id,
            "action": self.action,
            "target_collection": self.target_collection,
            "target_key": self.target_key,
            "source_index": self.source_index,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class CeqanetWritePlan:
    """Non-mutating write plan for a CEQAnet persistence preview."""

    operations: tuple[CeqanetWriteOperation, ...]
    skipped_items: tuple[dict[str, object], ...]

    @property
    def operation_count(self) -> int:
        """Return number of planned operations."""

        return len(self.operations)

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe write plan payload."""

        counts_by_target: dict[str, int] = {
            "ceqa_records": 0,
            "sites": 0,
            "entities": 0,
        }
        for operation in self.operations:
            counts_by_target[operation.target_collection] += 1

        return {
            "metadata": {
                "schema_version": "ceqanet_write_plan.v1",
                "operation_count": self.operation_count,
                "skipped_item_count": len(self.skipped_items),
                "counts_by_target": counts_by_target,
                "action": "upsert_preview",
                "network_executed": False,
                "database_opened": False,
                "persistence_mutated": False,
            },
            "operations": [operation.to_dict() for operation in self.operations],
            "skipped_items": list(self.skipped_items),
        }


def build_ceqanet_write_plan(preview_payload: dict[str, Any]) -> CeqanetWritePlan:
    """Build a non-mutating write plan from CEQAnet persistence preview JSON."""

    metadata = preview_payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Persistence preview must contain metadata.")
    schema_version = metadata.get("schema_version")
    if schema_version != "ceqanet_persistence_preview.v1":
        raise ValueError(
            "Persistence preview schema_version must be ceqanet_persistence_preview.v1."
        )

    operations: list[CeqanetWriteOperation] = []
    skipped_items: list[dict[str, object]] = []

    for target_collection, key_field in (
        ("ceqa_records", "ceqa_key"),
        ("sites", "site_key"),
        ("entities", "entity_key"),
    ):
        collection = preview_payload.get(target_collection)
        if not isinstance(collection, list):
            raise ValueError(f"Persistence preview must contain {target_collection} list.")
        operations.extend(
            _operations_for_collection(
                collection,
                target_collection=cast(TargetCollection, target_collection),
                key_field=key_field,
                skipped_items=skipped_items,
            )
        )

    return CeqanetWritePlan(operations=tuple(operations), skipped_items=tuple(skipped_items))


def _operations_for_collection(
    collection: list[object],
    *,
    target_collection: TargetCollection,
    key_field: str,
    skipped_items: list[dict[str, object]],
) -> list[CeqanetWriteOperation]:
    """Build operation previews for one collection."""

    operations: list[CeqanetWriteOperation] = []
    for source_index, item in enumerate(collection):
        if not isinstance(item, dict):
            skipped_items.append(
                {
                    "target_collection": target_collection,
                    "source_index": source_index,
                    "reason": "item is not an object",
                }
            )
            continue
        payload = cast(dict[str, Any], item)
        target_key = _string_or_none(payload.get(key_field))
        if target_key is None:
            skipped_items.append(
                {
                    "target_collection": target_collection,
                    "source_index": source_index,
                    "reason": f"missing {key_field}",
                }
            )
            continue
        operations.append(
            CeqanetWriteOperation(
                operation_id=f"{target_collection}:{target_key}",
                action="upsert_preview",
                target_collection=target_collection,
                target_key=target_key,
                source_index=source_index,
                payload=payload,
            )
        )
    return operations


def _string_or_none(value: object) -> str | None:
    """Return non-empty string value or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
