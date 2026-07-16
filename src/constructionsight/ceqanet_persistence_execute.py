"""Atomic CEQAnet persistence execution for previously reviewed write plans.

The complete write plan is validated before the database is initialized or opened for
mutation. Every operation is then applied in one transaction. Unsupported, malformed,
or failing operations abort the whole plan rather than committing a partial result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast

from sqlalchemy import Engine

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.entity_models import Entity
from constructionsight.site_models import Site
from constructionsight.storage.database import (
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.domain_store import CeqaStore, EntityStore, SiteStore

SupportedTarget = Literal["ceqa_records", "sites", "entities"]
PreparedModel = CeqaRecord | Site | Entity


@dataclass(frozen=True)
class CeqanetPersistenceExecutionResult:
    """Result from one completely applied CEQAnet write plan."""

    applied_operations: tuple[dict[str, object], ...]
    failed_operations: tuple[dict[str, object], ...] = ()
    skipped_operations: tuple[dict[str, object], ...] = ()

    @property
    def applied_count(self) -> int:
        return len(self.applied_operations)

    @property
    def failed_count(self) -> int:
        return len(self.failed_operations)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped_operations)

    def to_dict(self) -> dict[str, object]:
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
                "schema_version": "ceqanet_persistence_execution.v2",
                "transactional": True,
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


@dataclass(frozen=True)
class _PreparedOperation:
    operation_id: str
    source_index: int
    target: SupportedTarget
    target_key: object
    model: PreparedModel


def execute_ceqanet_write_plan(
    write_plan_payload: dict[str, Any],
    *,
    engine: Engine,
    initialize: bool = True,
) -> CeqanetPersistenceExecutionResult:
    """Validate and atomically apply one complete CEQAnet write plan."""

    operations = _prepare_operations(write_plan_payload)
    if initialize:
        initialize_database(engine)

    factory = session_factory(engine)
    applied: list[dict[str, object]] = []
    current_operation = "none"
    try:
        with managed_session(factory) as session:
            ceqa_store = CeqaStore(session)
            site_store = SiteStore(session)
            entity_store = EntityStore(session)
            for operation in operations:
                current_operation = operation.operation_id
                _apply_prepared_operation(
                    operation,
                    ceqa_store=ceqa_store,
                    site_store=site_store,
                    entity_store=entity_store,
                )
                applied.append(
                    {
                        "operation_id": operation.operation_id,
                        "source_index": operation.source_index,
                        "target_collection": operation.target,
                        "target_key": operation.target_key,
                        "action": "upsert_preview",
                    }
                )
    except Exception as exc:
        raise ValueError(
            "CEQAnet write-plan transaction failed and was rolled back; "
            f"operation={current_operation}, error={exc.__class__.__name__}"
        ) from exc

    return CeqanetPersistenceExecutionResult(applied_operations=tuple(applied))


def validate_ceqanet_write_plan(write_plan_payload: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
    """Validate one complete plan without opening a database."""

    prepared = _prepare_operations(write_plan_payload)
    return len(prepared), tuple(operation.operation_id for operation in prepared)


def _prepare_operations(write_plan_payload: dict[str, Any]) -> tuple[_PreparedOperation, ...]:
    _validate_write_plan_envelope(write_plan_payload)
    raw_operations = write_plan_payload["operations"]
    assert isinstance(raw_operations, list)
    prepared: list[_PreparedOperation] = []
    identifiers: set[str] = set()
    for index, raw_operation in enumerate(raw_operations):
        if not isinstance(raw_operation, dict):
            raise ValueError(f"write-plan operation {index} must be an object")
        operation = cast(dict[str, Any], raw_operation)
        operation_id = _string_or_none(operation.get("operation_id"))
        if operation_id is None:
            raise ValueError(f"write-plan operation {index} requires operation_id")
        if operation_id in identifiers:
            raise ValueError(f"duplicate write-plan operation_id: {operation_id}")
        identifiers.add(operation_id)
        if operation.get("action") != "upsert_preview":
            raise ValueError(f"write-plan operation {operation_id} has unsupported action")
        target = operation.get("target_collection")
        if target not in {"ceqa_records", "sites", "entities"}:
            raise ValueError(
                f"write-plan operation {operation_id} has unsupported target_collection"
            )
        payload = operation.get("payload")
        if not isinstance(payload, dict):
            raise ValueError(f"write-plan operation {operation_id} payload must be an object")
        try:
            model = _validate_target_payload(
                cast(SupportedTarget, target),
                cast(dict[str, Any], payload),
            )
        except ValueError as exc:
            raise ValueError(
                f"write-plan operation {operation_id} payload is invalid: {exc.__class__.__name__}"
            ) from exc
        prepared.append(
            _PreparedOperation(
                operation_id=operation_id,
                source_index=_source_index(operation.get("source_index"), index),
                target=cast(SupportedTarget, target),
                target_key=operation.get("target_key"),
                model=model,
            )
        )
    return tuple(prepared)


def _validate_write_plan_envelope(write_plan_payload: dict[str, Any]) -> None:
    metadata = write_plan_payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("Write plan must contain metadata.")
    if metadata.get("schema_version") != "ceqanet_write_plan.v1":
        raise ValueError("Write plan schema_version must be ceqanet_write_plan.v1.")
    operations = write_plan_payload.get("operations")
    if not isinstance(operations, list):
        raise ValueError("Write plan must contain operations list.")
    declared_count = metadata.get("operation_count")
    if not isinstance(declared_count, int) or declared_count != len(operations):
        raise ValueError("Write plan operation_count must equal operations length.")
    skipped_count = metadata.get("skipped_item_count")
    skipped_items = write_plan_payload.get("skipped_items")
    if not isinstance(skipped_count, int) or skipped_count != 0:
        raise ValueError("Reviewed write plan cannot contain skipped items.")
    if skipped_items != []:
        raise ValueError("Reviewed write plan skipped_items must be empty.")
    if metadata.get("network_executed") is not False:
        raise ValueError("Write plan must affirm network_executed=false.")
    if metadata.get("database_opened") is not False:
        raise ValueError("Write plan must affirm database_opened=false.")
    if metadata.get("persistence_mutated") is not False:
        raise ValueError("Write plan must affirm persistence_mutated=false.")


def _validate_target_payload(
    target: SupportedTarget,
    payload: dict[str, Any],
) -> PreparedModel:
    if target == "ceqa_records":
        return CeqaRecord.model_validate(payload)
    if target == "sites":
        return Site.model_validate(payload)
    return Entity.model_validate(payload)


def _apply_prepared_operation(
    operation: _PreparedOperation,
    *,
    ceqa_store: CeqaStore,
    site_store: SiteStore,
    entity_store: EntityStore,
) -> None:
    if operation.target == "ceqa_records":
        if not isinstance(operation.model, CeqaRecord):
            raise TypeError("prepared CEQA operation has the wrong model type")
        ceqa_store.upsert(operation.model)
        return
    if operation.target == "sites":
        if not isinstance(operation.model, Site):
            raise TypeError("prepared site operation has the wrong model type")
        site_store.upsert(operation.model)
        return
    if not isinstance(operation.model, Entity):
        raise TypeError("prepared entity operation has the wrong model type")
    entity_store.upsert(operation.model)


def _source_index(value: object, fallback: int) -> int:
    return value if isinstance(value, int) and value >= 0 else fallback


def _string_or_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
