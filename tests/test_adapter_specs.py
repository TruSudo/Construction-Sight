from constructionsight.adapters.specs import (
    AdapterImplementationStatus,
    default_adapter_family_specs,
)
from constructionsight.models import PlatformFamily, RecordCategory


def test_default_adapter_family_specs_cover_registered_platforms() -> None:
    specs = default_adapter_family_specs()

    assert PlatformFamily.CEQANET in specs
    assert PlatformFamily.CSLB in specs
    assert PlatformFamily.ACCELA_ACA in specs
    assert PlatformFamily.TYLER_ENERGOV in specs
    assert PlatformFamily.GRANICUS_LEGISTAR in specs
    assert PlatformFamily.CIVICPLUS_PRIMEGOV in specs
    assert PlatformFamily.LASERFICHE in specs
    assert PlatformFamily.CUSTOM_REPORT in specs


def test_default_adapter_family_specs_are_not_live_yet() -> None:
    specs = default_adapter_family_specs()

    assert all(spec.is_live is False for spec in specs.values())


def test_ceqanet_spec_is_contract_ready_but_not_live() -> None:
    specs = default_adapter_family_specs()
    ceqanet = specs[PlatformFamily.CEQANET]

    assert ceqanet.status is AdapterImplementationStatus.CONTRACT_READY
    assert ceqanet.is_live is False
    assert RecordCategory.CEQA in ceqanet.expected_categories
    assert RecordCategory.DOCUMENT in ceqanet.expected_categories


def test_remaining_non_ceqanet_specs_are_placeholders() -> None:
    specs = default_adapter_family_specs()

    for platform_family, spec in specs.items():
        if platform_family is PlatformFamily.CEQANET:
            continue
        assert spec.status is AdapterImplementationStatus.PLACEHOLDER


def test_accela_and_energov_specs_declare_javascript_public_portals() -> None:
    specs = default_adapter_family_specs()

    accela = specs[PlatformFamily.ACCELA_ACA]
    energov = specs[PlatformFamily.TYLER_ENERGOV]

    assert accela.requires_javascript is True
    assert energov.requires_javascript is True
    assert RecordCategory.PERMIT in accela.expected_categories
    assert RecordCategory.PLANNING_CASE in energov.expected_categories


def test_agenda_document_specs_declare_pdf_processing() -> None:
    specs = default_adapter_family_specs()

    assert specs[PlatformFamily.GRANICUS_LEGISTAR].requires_pdf_processing is True
    assert specs[PlatformFamily.CIVICPLUS_PRIMEGOV].requires_pdf_processing is True
    assert specs[PlatformFamily.LASERFICHE].requires_pdf_processing is True
    assert RecordCategory.DOCUMENT in specs[PlatformFamily.LASERFICHE].expected_categories
