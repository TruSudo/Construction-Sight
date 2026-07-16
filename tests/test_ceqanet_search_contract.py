from datetime import date

from constructionsight.adapters.ceqanet import CEQANET_SEARCH_URL
from constructionsight.adapters.ceqanet_search_contract import (
    CEQANET_HIGH_SIGNAL_DOCUMENT_TYPES,
    CeqanetAdvancedSearchFormContract,
    build_ceqanet_advanced_search_params,
    normalize_ceqanet_document_type,
)


def test_ceqanet_advanced_search_contract_matches_public_form_fields() -> None:
    contract = CeqanetAdvancedSearchFormContract()

    assert contract.action_url == CEQANET_SEARCH_URL
    assert contract.method == "GET"
    assert contract.start_range_field == "StartRange"
    assert contract.end_range_field == "EndRange"
    assert contract.document_type_field == "DocumentType"
    assert contract.lead_agency_field == "LeadAgency"
    assert contract.county_field == "County"
    assert contract.city_field == "City"
    assert contract.region_field == "Region"
    assert contract.local_action_field == "LocalAction"
    assert contract.project_issue_field == "ProjectIssue"
    assert contract.development_type_field == "DevelopmentType"


def test_normalize_ceqanet_document_type_expands_known_codes() -> None:
    assert normalize_ceqanet_document_type("EIR") == "EIR - Draft EIR"
    assert normalize_ceqanet_document_type("mnd") == ("MND - Mitigated Negative Declaration")
    assert normalize_ceqanet_document_type("NOP") == ("NOP - Notice of Preparation of a Draft EIR")
    assert normalize_ceqanet_document_type("Custom Label") == "Custom Label"


def test_build_ceqanet_advanced_search_params_uses_real_field_names() -> None:
    params = build_ceqanet_advanced_search_params(
        counties=("San Bernardino",),
        document_types=("EIR",),
        lead_agencies=("City of Fontana",),
        start_range=date(2026, 1, 1),
        end_range=date(2026, 1, 31),
        state_review_period_end=date(2026, 2, 1),
        public_review_period_end=date(2026, 2, 28),
    )

    assert params == (
        ("StartRange", "2026-01-01"),
        ("EndRange", "2026-01-31"),
        ("DocumentType", "EIR - Draft EIR"),
        ("LeadAgency", "City of Fontana"),
        ("County", "San Bernardino"),
        ("StateReviewPeriodEnd", "2026-02-01"),
        ("PublicReviewPeriodEnd", "2026-02-28"),
    )


def test_build_ceqanet_advanced_search_params_expands_signal_types() -> None:
    params = build_ceqanet_advanced_search_params(
        counties=("San Bernardino",),
        high_signal_only=True,
    )
    expected_document_types = [
        ("DocumentType", document_type) for document_type in CEQANET_HIGH_SIGNAL_DOCUMENT_TYPES
    ]

    assert params == tuple(expected_document_types + [("County", "San Bernardino")])
