"""CEQAnet advanced-search form contract.

The field names in this module are derived from the public CEQAnet Advanced
Search form. The form submits with GET to `/Search`; option elements without a
value attribute submit their visible label text as the value under normal HTML
form semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from constructionsight.adapters.ceqanet import CEQANET_SEARCH_URL


CEQANET_ADVANCED_SEARCH_ACTION_URL = CEQANET_SEARCH_URL

CEQANET_FIELD_START_RANGE = "StartRange"
CEQANET_FIELD_END_RANGE = "EndRange"
CEQANET_FIELD_DOCUMENT_TYPE = "DocumentType"
CEQANET_FIELD_LEAD_AGENCY = "LeadAgency"
CEQANET_FIELD_STATE_REVIEW_AGENCY = "StateReviewAgency"
CEQANET_FIELD_COUNTY = "County"
CEQANET_FIELD_CITY = "City"
CEQANET_FIELD_REGION = "Region"
CEQANET_FIELD_LOCAL_ACTION = "LocalAction"
CEQANET_FIELD_PROJECT_ISSUE = "ProjectIssue"
CEQANET_FIELD_DEVELOPMENT_TYPE = "DevelopmentType"
CEQANET_FIELD_STATE_REVIEW_PERIOD_END = "StateReviewPeriodEnd"
CEQANET_FIELD_PUBLIC_REVIEW_PERIOD_END = "PublicReviewPeriodEnd"

CEQANET_HIGH_SIGNAL_DOCUMENT_TYPES = (
    "EIR - Draft EIR",
    "MND - Mitigated Negative Declaration",
    "NEG - Negative Declaration",
    "NOP - Notice of Preparation of a Draft EIR",
    "NOC - Other Notice of Completion",
)

CEQANET_DOCUMENT_TYPE_ALIASES = {
    "ADM": "ADM - Addendum",
    "BIA": "BIA - Tribal Notice of Decision",
    "BLA": "BLA - Bureau of Indian Affairs Notice of Land Acquisition",
    "CON": "CON - Early Consultation",
    "EA": "EA  - Environmental Assessment",
    "EIR": "EIR - Draft EIR",
    "EIS": "EIS - Draft EIS",
    "FED": "FED - Functional Equivalent Document",
    "FIN": "FIN - Final Document",
    "FIS": "FIS - Final Environmental Statement",
    "FON": "FON - FONSI - Findings of No Significant Impact",
    "FOT": "FOT - Federal Other Document",
    "FYI": "FYI - Information Only",
    "JD": "JD  - Joint Document",
    "MEA": "MEA - Master Environmental Assessment",
    "MND": "MND - Mitigated Negative Declaration",
    "NDE": "NDE - Notice of Decision",
    "NEG": "NEG - Negative Declaration",
    "NOC": "NOC - Other Notice of Completion",
    "NOD": "NOD - Notice of Determination",
    "NOE": "NOE - Notice of Exemption",
    "NOI": "NOI - Notice of Intent",
    "NOP": "NOP - Notice of Preparation of a Draft EIR",
}


@dataclass(frozen=True)
class CeqanetAdvancedSearchFormContract:
    """Machine-readable contract for the public CEQAnet advanced search form."""

    action_url: str = CEQANET_ADVANCED_SEARCH_ACTION_URL
    method: str = "GET"
    start_range_field: str = CEQANET_FIELD_START_RANGE
    end_range_field: str = CEQANET_FIELD_END_RANGE
    document_type_field: str = CEQANET_FIELD_DOCUMENT_TYPE
    lead_agency_field: str = CEQANET_FIELD_LEAD_AGENCY
    state_review_agency_field: str = CEQANET_FIELD_STATE_REVIEW_AGENCY
    county_field: str = CEQANET_FIELD_COUNTY
    city_field: str = CEQANET_FIELD_CITY
    region_field: str = CEQANET_FIELD_REGION
    local_action_field: str = CEQANET_FIELD_LOCAL_ACTION
    project_issue_field: str = CEQANET_FIELD_PROJECT_ISSUE
    development_type_field: str = CEQANET_FIELD_DEVELOPMENT_TYPE
    state_review_period_end_field: str = CEQANET_FIELD_STATE_REVIEW_PERIOD_END
    public_review_period_end_field: str = CEQANET_FIELD_PUBLIC_REVIEW_PERIOD_END


def normalize_ceqanet_document_type(value: str) -> str:
    """Return the CEQAnet option-label value for a document-type input."""

    normalized = " ".join(value.strip().split())
    if not normalized:
        return normalized
    return CEQANET_DOCUMENT_TYPE_ALIASES.get(normalized.upper(), normalized)


def build_ceqanet_advanced_search_params(
    *,
    counties: tuple[str, ...] = (),
    document_types: tuple[str, ...] = (),
    lead_agencies: tuple[str, ...] = (),
    start_range: date | None = None,
    end_range: date | None = None,
    state_review_period_end: date | None = None,
    public_review_period_end: date | None = None,
    high_signal_only: bool = False,
    contract: CeqanetAdvancedSearchFormContract = CeqanetAdvancedSearchFormContract(),
) -> tuple[tuple[str, str], ...]:
    """Build deterministic CEQAnet advanced-search GET parameters."""

    params: list[tuple[str, str]] = []
    if start_range:
        params.append((contract.start_range_field, start_range.isoformat()))
    if end_range:
        params.append((contract.end_range_field, end_range.isoformat()))
    selected_document_types = _document_type_values(
        document_types=document_types,
        high_signal_only=high_signal_only,
    )
    params.extend(
        (contract.document_type_field, document_type) for document_type in selected_document_types
    )
    params.extend((contract.lead_agency_field, lead_agency) for lead_agency in lead_agencies)
    params.extend((contract.county_field, county) for county in counties)
    if state_review_period_end:
        params.append((contract.state_review_period_end_field, state_review_period_end.isoformat()))
    if public_review_period_end:
        params.append((contract.public_review_period_end_field, public_review_period_end.isoformat()))
    return tuple(params)


def _document_type_values(
    *,
    document_types: tuple[str, ...],
    high_signal_only: bool,
) -> tuple[str, ...]:
    """Return normalized CEQAnet document-type option labels."""

    if high_signal_only and not document_types:
        return CEQANET_HIGH_SIGNAL_DOCUMENT_TYPES
    return tuple(normalize_ceqanet_document_type(value) for value in document_types)
