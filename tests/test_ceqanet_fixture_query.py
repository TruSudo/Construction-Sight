from datetime import date

import pytest
from constructionsight.ceqa_models import CeqaRecord

from constructionsight.adapters.ceqanet_query import (
    CeqanetFixtureQuery,
    CeqanetFixtureQueryService,
)


def _record(
    key: str,
    *,
    title: str,
    county: str,
    document_type: str,
    lead_agency: str,
    received_date: date | None,
    posted_date: date | None,
    description: str = "",
    project_location: str = "",
    sch_number: str | None = None,
) -> CeqaRecord:
    return CeqaRecord(
        ceqa_key=key,
        title=title,
        county=county,
        lead_agency=lead_agency,
        document_type=document_type,
        state_clearinghouse_number=sch_number,
        received_date=received_date,
        posted_date=posted_date,
        description=description,
        project_location=project_location,
    )


def _records() -> list[CeqaRecord]:
    return [
        _record(
            "ceqanet:sch:2026000001",
            title="North Fontana Logistics Center",
            county="San Bernardino",
            document_type="EIR",
            lead_agency="City of Fontana",
            received_date=date(2026, 1, 10),
            posted_date=date(2026, 1, 12),
            description="Warehouse logistics project near Sierra Avenue.",
            project_location="Fontana, CA",
            sch_number="2026000001",
        ),
        _record(
            "ceqanet:sch:2026000002",
            title="Riverside Residential Infill",
            county="Riverside",
            document_type="Notice of Exemption",
            lead_agency="City of Riverside",
            received_date=date(2026, 2, 5),
            posted_date=date(2026, 2, 8),
            description="Residential infill project.",
            project_location="Riverside, CA",
            sch_number="2026000002",
        ),
        _record(
            "ceqanet:sch:2026000003",
            title="Redlands Commerce Park",
            county="San Bernardino",
            document_type="MND",
            lead_agency="City of Redlands",
            received_date=date(2026, 3, 15),
            posted_date=date(2026, 3, 20),
            description="Commerce park and light industrial project.",
            project_location="Redlands, CA",
            sch_number="2026000003",
        ),
    ]


def test_ceqanet_fixture_query_filters_by_county_and_high_signal_documents() -> None:
    result = CeqanetFixtureQueryService().query(
        _records(),
        CeqanetFixtureQuery(counties=("san bernardino",), high_signal_only=True),
    )

    assert result.source_record_count == 3
    assert result.matched_record_count == 2
    assert result.truncated is False
    assert {record.ceqa_key for record in result.records} == {
        "ceqanet:sch:2026000001",
        "ceqanet:sch:2026000003",
    }


def test_ceqanet_fixture_query_filters_by_document_type_and_lead_agency() -> None:
    result = CeqanetFixtureQueryService().query(
        _records(),
        CeqanetFixtureQuery(
            document_types=("eir",),
            lead_agencies=("City of Fontana",),
        ),
    )

    assert result.matched_record_count == 1
    assert result.records[0].title == "North Fontana Logistics Center"


def test_ceqanet_fixture_query_filters_by_received_and_posted_dates() -> None:
    result = CeqanetFixtureQueryService().query(
        _records(),
        CeqanetFixtureQuery(
            received_from=date(2026, 2, 1),
            posted_to=date(2026, 3, 1),
        ),
    )

    assert result.matched_record_count == 1
    assert result.records[0].county == "Riverside"


def test_ceqanet_fixture_query_requires_all_text_terms() -> None:
    result = CeqanetFixtureQueryService().query(
        _records(),
        CeqanetFixtureQuery(text_terms=("commerce", "industrial")),
    )

    assert result.matched_record_count == 1
    assert result.records[0].title == "Redlands Commerce Park"


def test_ceqanet_fixture_query_limit_marks_truncation() -> None:
    result = CeqanetFixtureQueryService().query(
        _records(),
        CeqanetFixtureQuery(counties=("san bernardino",), limit=1),
    )

    assert result.matched_record_count == 1
    assert result.truncated is True
    assert len(result.records) == 1


def test_ceqanet_fixture_query_rejects_invalid_limit() -> None:
    with pytest.raises(ValueError, match="limit must be at least 1"):
        CeqanetFixtureQuery(limit=0)
