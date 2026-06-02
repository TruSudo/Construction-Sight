"""Adapter execution runner for ConstructionSight."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from constructionsight.adapters.base import (
    AdapterError,
    AdapterOperationResult,
    AdapterOutcome,
    AdapterRunContext,
    SourceAdapter,
)
from constructionsight.adapters.registry import AdapterRegistry, default_adapter_registry
from constructionsight.legal import AccessDecision
from constructionsight.models import PublicSource


class AdapterRunner:
    """Run adapters through the standard preflight/list/extract/normalize lifecycle."""

    def __init__(self, registry: AdapterRegistry | None = None) -> None:
        self.registry = registry or default_adapter_registry()

    def run_source(
        self,
        source: PublicSource,
        context: AdapterRunContext | None = None,
    ) -> AdapterOperationResult[BaseModel]:
        """Run the registered adapter for a source and return normalized records."""

        adapter = self.registry.create(source, context)
        return self.run_adapter(adapter)

    def run_adapter(self, adapter: SourceAdapter[Any, BaseModel]) -> AdapterOperationResult[BaseModel]:
        """Run an adapter instance through the standard lifecycle."""

        preflight = adapter.preflight()
        if preflight.decision is not AccessDecision.ALLOWED:
            return adapter.blocked_result("run_adapter", preflight)

        try:
            adapter.discover_search()
            raw_records = list(adapter.list_records())
            if adapter.context.max_records is not None:
                raw_records = raw_records[: adapter.context.max_records]

            normalized: list[BaseModel] = []
            for raw_record in raw_records:
                detailed = adapter.extract_record_detail(raw_record)
                normalized.append(adapter.normalize(detailed))

            return AdapterOperationResult(
                source_name=adapter.source_name,
                operation="run_adapter",
                outcome=AdapterOutcome.SUCCESS,
                records=tuple(normalized),
            )
        except Exception as exc:
            return AdapterOperationResult(
                source_name=adapter.source_name,
                operation="run_adapter",
                outcome=AdapterOutcome.FAILED,
                errors=(
                    AdapterError(
                        source_name=adapter.source_name,
                        operation="run_adapter",
                        message=str(exc),
                        recoverable=False,
                        details={"exception_type": exc.__class__.__name__},
                    ),
                ),
            )
