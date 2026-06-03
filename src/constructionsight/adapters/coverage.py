"""Source-registry adapter coverage audit utilities."""

from __future__ import annotations

from dataclasses import dataclass

from constructionsight.adapters.registry import AdapterRegistry
from constructionsight.adapters.specs import AdapterFamilySpec
from constructionsight.models import PlatformFamily, PublicSource


@dataclass(frozen=True)
class SourceAdapterCoverageIssue:
    """Coverage issue for one source registry record."""

    source_name: str
    platform_family: PlatformFamily
    issue: str


@dataclass(frozen=True)
class SourceAdapterCoverageResult:
    """Coverage result for a source registry against adapters and specs."""

    source_count: int
    issues: tuple[SourceAdapterCoverageIssue, ...]

    @property
    def passed(self) -> bool:
        """Return true when all sources have adapter and spec coverage."""

        return not self.issues


def audit_source_adapter_coverage(
    sources: list[PublicSource],
    registry: AdapterRegistry,
    specs: dict[PlatformFamily, AdapterFamilySpec],
) -> SourceAdapterCoverageResult:
    """Verify every configured source has adapter and specification coverage."""

    issues: list[SourceAdapterCoverageIssue] = []
    supported = set(registry.supported_platforms())
    specified = set(specs)

    for source in sources:
        if source.platform_family not in supported:
            issues.append(
                SourceAdapterCoverageIssue(
                    source_name=source.source_name,
                    platform_family=source.platform_family,
                    issue="missing adapter registration",
                )
            )
        if source.platform_family not in specified:
            issues.append(
                SourceAdapterCoverageIssue(
                    source_name=source.source_name,
                    platform_family=source.platform_family,
                    issue="missing adapter family specification",
                )
            )

    return SourceAdapterCoverageResult(source_count=len(sources), issues=tuple(issues))
