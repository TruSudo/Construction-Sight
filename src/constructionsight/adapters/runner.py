"""Adapter execution runner for ConstructionSight."""

from __future__ import annotations

from itertools import islice
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

_MAX_ADAPTER_RECORDS = 5_000


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

    def run_adapter(
        self, adapter: SourceAdapter[Any, BaseModel]
    ) -> AdapterOperationResult[BaseModel]:
        """Run an adapter instance through the standard lifecycle."""

        try:
            limit = adapter.context.max_records
            if limit is None:
                limit = _MAX_ADAPTER_RECORDS
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise ValueError("adapter max_records must be an integer")
            if not 0 <= limit <= _MAX_ADAPTER_RECORDS:
                raise ValueError(
                    f"adapter max_records must be between 0 and {_MAX_ADAPTER_RECORDS}"
                )
            if adapter.context.dry_run and limit == 0:
                return AdapterOperationResult(
                    source_name=adapter.source_name,
                    operation="run_adapter",
                    outcome=AdapterOutcome.SUCCESS,
                    records=(),
                    notes="Dry run requested zero records; no source access was performed.",
                )

            if adapter.requires_access_preflight:
                preflight = adapter.preflight()
                if preflight.decision is not AccessDecision.ALLOWED:
                    return adapter.blocked_result("run_adapter", preflight)

            adapter.discover_search()
            normalized: list[BaseModel] = []
            for raw_record in islice(adapter.list_records(), limit):
                detailed = adapter.extract_record_detail(raw_record)
                normalized.append(adapter.normalize(detailed))

            return AdapterOperationResult(
                source_name=adapter.source_name,
                operation="run_adapter",
                outcome=AdapterOutcome.SUCCESS,
                records=tuple(normalized),
                notes=(
                    f"Processed at most {limit} raw records; "
                    "source enumeration may contain further records."
                ),
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
