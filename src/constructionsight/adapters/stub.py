"""Non-network placeholder adapters for registered platform families.

These adapters define platform-specific contracts without performing live
collection. They are intentionally safe scaffolds for Phase 5 registry/factory
validation before Phase 6 live adapters are implemented.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from constructionsight.adapters.base import AdapterSearchDescriptor, SourceAdapter
from constructionsight.models import PlatformFamily, SourceVerificationResult
from constructionsight.site_models import Site


class StubPlatformAdapter(SourceAdapter[dict[str, Any], Site]):
    """Safe placeholder adapter for a platform family."""

    platform_family: PlatformFamily = PlatformFamily.UNKNOWN

    def verify_source(self) -> SourceVerificationResult:
        """Return a non-network placeholder verification result."""

        return SourceVerificationResult(
            source_name=self.source_name,
            public_url=self.source.public_url,
            url_reachable=False,
            portal_type_detected=self.platform_family,
            confidence_score=0,
            notes="Placeholder adapter only; live verification is handled by SourceVerifier.",
        )

    def discover_search(self) -> list[AdapterSearchDescriptor]:
        """Return a placeholder public search descriptor."""

        return [
            AdapterSearchDescriptor(
                source_name=self.source_name,
                search_name=f"{self.platform_family.value} placeholder search",
                public_url=str(self.source.public_url),
                method="GET",
                record_types=[category.value for category in self.source.record_categories],
                notes="Placeholder descriptor for adapter-family contract validation.",
            )
        ]

    def list_records(self) -> Iterable[dict[str, Any]]:
        """Return no records because this placeholder performs no collection."""

        return ()

    def extract_record_detail(self, record: dict[str, Any]) -> dict[str, Any]:
        """Return the record unchanged."""

        return record

    def normalize(self, record: dict[str, Any]) -> Site:
        """Normalize a synthetic site-like record for contract testing."""

        return Site.model_validate(record)


class CeqanetAdapter(StubPlatformAdapter):
    """Placeholder CEQAnet adapter contract."""

    platform_family = PlatformFamily.CEQANET


class CslbAdapter(StubPlatformAdapter):
    """Placeholder CSLB adapter contract."""

    platform_family = PlatformFamily.CSLB


class AccelaAcaAdapter(StubPlatformAdapter):
    """Placeholder Accela ACA adapter contract."""

    platform_family = PlatformFamily.ACCELA_ACA


class TylerEnergovAdapter(StubPlatformAdapter):
    """Placeholder Tyler EnerGov adapter contract."""

    platform_family = PlatformFamily.TYLER_ENERGOV


class GranicusLegistarAdapter(StubPlatformAdapter):
    """Placeholder Granicus/Legistar adapter contract."""

    platform_family = PlatformFamily.GRANICUS_LEGISTAR


class CivicplusPrimegovAdapter(StubPlatformAdapter):
    """Placeholder CivicPlus/PrimeGov adapter contract."""

    platform_family = PlatformFamily.CIVICPLUS_PRIMEGOV


class LaserficheAdapter(StubPlatformAdapter):
    """Placeholder Laserfiche adapter contract."""

    platform_family = PlatformFamily.LASERFICHE


class CustomReportAdapter(StubPlatformAdapter):
    """Placeholder custom municipal report adapter contract."""

    platform_family = PlatformFamily.CUSTOM_REPORT
