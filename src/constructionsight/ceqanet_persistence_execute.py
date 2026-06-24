"""Guarded CEQAnet persistence execution service.

This module applies previously reviewed CEQAnet write-plan operations to the
normalized SQLite-backed domain stores. It performs no network requests and no
document downloads. Callers are responsible for requiring explicit operator
consent before invoking this mutating service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from sqlalchemy import Engine

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.entity_models import Entity
from constructionsight.site_models import Site
from constructionsight.storage.database import initialize_database, managed_session, session_factory
from constructionsight.storage.domain_store import CeqaStore, EntityStore, SiteStore

SupportedTarget = Literal["ceqa_records", "sites", "entities"]


@dataclass(frozen=True)
class CeqanetPersistenceExecutionResult:
    """Result from applying a CEQAnet write plan to persistence."""

    applied_operations: tuple[dict[str, object], ...]
    failed_operations: tuple[dict[str, object], ...]
    skipped_operations: tuple[dict[str, object], ...]

    @property
    def applied_count(self) -> int:
        """Return successfully applied operation count."""

        return len(self.applied_operations)

    @property
    def failed_count(self) -> int:
        """Return failed operation count."""

        return len(self.failed_operations)

    @property
    def skipped_count(self) -> int:
        """Return skipped operation count."""

        return len(self.skipped_operations)

    def to_dict(self) -> dict[str, object]:
        """Return deterministic JSON-safe execution result."""

        counts_by_target: dict[str, int] = {
            "ceqa_records": 0,
            "sites": 0,
            "entities": 0,
        }
        for operation in self.applied_operations:
            target = operation.get("target_collection")
            if isinstance(target, str) and target in counts_by_target:
                counts_by_target[target] += 1

        return {
            "metadata": {
                "schema_version": "ceqanet_persistence_execution.v1",
                "applied_count": self.applied_count,
                "failed_count": self.failed_count,
                "skipped_count": self.skipped_count,
                "counts_by_target": counts_by_target,
                "network_executed": False,
                "database_opened": True,
                "persistence_mutated": self.applied_count > 0,
            },
            "applied_operations": list(self.applied_operations),
            "failed_operations": list(self.failed_operations),
            "skipped_operations": list(self.skipped_operations),
        }


def execute_ceqanet_write_plan(
    write_plan_payload: dict[str, Any],
    *,
    engine: Engine,
    initialize: bool = True,
) -> CeqanetPersistenceExecutionResult:
    """Apply a CEQAnet write plan to normalized domain stores."""

    _validate_write_plan(write_plan_payload)
    operations = _operation_objects(write_plan_payload)

    if initialize:
        initialize_database(engine)

    factory = session_factory(engine)
    applied_operations: list[dict[str, object]] = []
    failed_operations: list[dict[str, object]] = []
    skipped_operations: list[dict[str, object]] = []

    with managed_session(factory) as session:
        ceqa_store = CeqaStore(session)
        site_store = SiteStore(session)
        entity_store = EntityStore(session)

        for index, operation in enumerate(operations):
            action = operation.get("action")
            target = operation.get("target_collection")
            operation_id = _string_or_none(operation.get("operation_id")) or f"operation:{index}"
            if action != "upsert_preview":
                skipped_operations.append(
                    {
                        "operation_id": operation_id,
                        "source_index": index,
                        "reason": "unsupported action",
                        "action": action,
                    }
                )
                continue
            if target not in {"ceqa_records", "sites", "entities"}:
                skipped_operations.append(
                    {
                        "operation_id": operation_id,
                        "source_index": index,
                        "reason": "unsupported target_collection",
                        "target_collection": target,
                    }
                )
                continue

            payload = operation.get("payload")
            if not isinstance(payload, dict):
                failed_operations.append(
                    {
                        "operation_id": operation_id,
                        "source_index": index,
                        "target_collection": target,
                        "reason": "payload is not an object",
                    }
                )
                continue

            try:
                _apply_operation(
                    target=cast(SupportedTarget, target),
                    payload=cast(dict[str, Any], payload),
                    ceqa_store=ceqa_store,
                    site_store=site_store,
                    entity_store=entity_store,
                )
            except ValueError as exc:
                failed_operations.append(
                    {
                        "operation_id": operation_id,
                        "source_index": index,
                        "target_collection": target,
                        "reason": str(exc),
                    }
                )
                continue

            applied_operations.append(
                {
                    "operation_id": operation_id,
                    "source_index": index,
                    "target_collection": target,
                    "target_key": operation.get("target_key"),
                    "action": "upsert_preview",
                }
            )

    return CeqanetPersistenceExecutionResult(
        applied_operations=tuple(applied_operations),
        failed_operations=tuple(failed_operations),
        skipped_operations=tuple(skipped_operations),
    )


def _validate_write_plan(write_plan_payload: dict[str, Any]) -> None:
    """Validate the top-level write-plan payload."""

    metadata = write_plan_payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Write plan must contain metadata.")
    schema_version = metadata.get("schema_version")
    if schema_version != "ceqanet_write_plan.v1":
        raise ValueError("Write plan schema_version must be ceqanet_write_plan.v1.")
    operations = write_plan_payload.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Write plan must contain operations list.")


def _operation_objects(write_plan_payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Return JSON object operations from a write plan."""

    operations = write_plan_payload["operations"]
    assert isinstance(operations, list)
    typed_operations: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            typed_operations.append(
                {
                    "operation_id": f"operation:{index}",
                    "action": "invalid",
                    "target_collection": "invalid",
                    "payload": None,
                }
            )
            continue
        typed_operations.append(cast(dict[str, Any], operation))
    return typed_operations


def _apply_operation(
    *,
    target: SupportedTarget,
    payload: dict[str, Any],
    ceqa_store: CeqaStore,
    site_store: SiteStore,
    entity_store: EntityStore,
) -> None:
    """Apply one validated write operation to the matching domain store."""

    try:
        if target == "ceqa_records":
            ceqa_store.upsert(CeqaRecord.model_validate(payload))
            return
        if target == "sites":
            site_store.upsert(Site.model_validate(payload))
            return
        entity_store.upsert(Entity.model_validate(payload))
    except Exception as exc:
        raise ValueError(exc.__class__.__name__) from exc


def _string_or_none(value: object) -> str | None:
    """Return non-empty string value or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
