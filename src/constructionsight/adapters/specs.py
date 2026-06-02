"""Adapter-family specifications for ConstructionSight."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from constructionsight.models import PlatformFamily, RecordCategory


class AdapterImplementationStatus(StrEnum):
    """Implementation maturity state for an adapter family."""

    PLACEHOLDER = "placeholder"
    CONTRACT_READY = "contract_ready"
    LIVE_READ_ONLY = "live_read_only"
    PRODUCTION_READY = "production_ready"


class AdapterFamilySpec(BaseModel):
    """Documented contract expectations for one adapter family."""

    platform_family: PlatformFamily
    status: AdapterImplementationStatus = AdapterImplementationStatus.PLACEHOLDER
    expected_categories: list[RecordCategory] = Field(default_factory=list)
    requires_javascript: bool = False
    requires_pdf_processing: bool = False
    uses_public_http: bool = True
    notes: str | None = None

    @property
    def is_live(self) -> bool:
        """Return true when this adapter family has live source execution support."""

        return self.status in {
            AdapterImplementationStatus.LIVE_READ_ONLY,
            AdapterImplementationStatus.PRODUCTION_READY,
        }


def default_adapter_family_specs() -> dict[PlatformFamily, AdapterFamilySpec]:
    """Return default adapter-family specifications."""

    return {
        PlatformFamily.CEQANET: AdapterFamilySpec(
            platform_family=PlatformFamily.CEQANET,
            expected_categories=[RecordCategory.CEQA, RecordCategory.DOCUMENT],
            notes="Placeholder contract for CEQAnet public environmental review records.",
        ),
        PlatformFamily.CSLB: AdapterFamilySpec(
            platform_family=PlatformFamily.CSLB,
            expected_categories=[RecordCategory.CONTRACTOR_LICENSE],
            notes="Placeholder contract for public contractor license records.",
        ),
        PlatformFamily.ACCELA_ACA: AdapterFamilySpec(
            platform_family=PlatformFamily.ACCELA_ACA,
            expected_categories=[RecordCategory.PERMIT, RecordCategory.PLANNING_CASE, RecordCategory.INSPECTION],
            requires_javascript=True,
            notes="Placeholder contract for Accela Citizen Access public portals.",
        ),
        PlatformFamily.TYLER_ENERGOV: AdapterFamilySpec(
            platform_family=PlatformFamily.TYLER_ENERGOV,
            expected_categories=[RecordCategory.PERMIT, RecordCategory.PLANNING_CASE, RecordCategory.INSPECTION],
            requires_javascript=True,
            notes="Placeholder contract for Tyler EnerGov public portals.",
        ),
        PlatformFamily.GRANICUS_LEGISTAR: AdapterFamilySpec(
            platform_family=PlatformFamily.GRANICUS_LEGISTAR,
            expected_categories=[RecordCategory.AGENDA, RecordCategory.DOCUMENT],
            requires_pdf_processing=True,
            notes="Placeholder contract for legislative agenda systems.",
        ),
        PlatformFamily.CIVICPLUS_PRIMEGOV: AdapterFamilySpec(
            platform_family=PlatformFamily.CIVICPLUS_PRIMEGOV,
            expected_categories=[RecordCategory.AGENDA, RecordCategory.DOCUMENT],
            requires_pdf_processing=True,
            notes="Placeholder contract for CivicPlus and PrimeGov agenda systems.",
        ),
        PlatformFamily.LASERFICHE: AdapterFamilySpec(
            platform_family=PlatformFamily.LASERFICHE,
            expected_categories=[RecordCategory.DOCUMENT, RecordCategory.AGENDA],
            requires_pdf_processing=True,
            notes="Placeholder contract for public document repositories.",
        ),
        PlatformFamily.CUSTOM_REPORT: AdapterFamilySpec(
            platform_family=PlatformFamily.CUSTOM_REPORT,
            expected_categories=[RecordCategory.PERMIT, RecordCategory.DOCUMENT, RecordCategory.AGENDA],
            requires_pdf_processing=True,
            notes="Placeholder contract for custom public report and document sources.",
        ),
    }
