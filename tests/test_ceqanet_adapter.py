import httpx

from constructionsight.adapters.ceqanet import (
    CEQANET_ADVANCED_SEARCH_URL,
    CeqanetAdapter,
    CeqanetFixtureParser,
    CeqanetLiveDiscovery,
)
from constructionsight.adapters.runner import AdapterRunner
from constructionsight.models import PublicSource


class MockCeqanetHttpClient:
    def __init__(self, response: httpx.Response | None = None, error: httpx.HTTPError | None = None) -> None:
        self.response = response
        self.error = error

    def get(self, url: str, *, follow_redirects: bool, timeout: float) -> httpx.Response:
        assert url == CEQANET_ADVANCED_SEARCH_URL
        assert follow_redirects is True
        assert timeout > 0
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _source() -> PublicSource:
    return PublicSource.model_validate(
        {
            "jurisdiction": {
                "name": "California State Clearinghouse",
                "county": "California",
                "state": "CA",
                "jurisdiction_type": "state",
            },
            "source_name": "CEQAnet State Clearinghouse",
            "source_type": "state_registry",
            "platform_family": "ceqanet",
            "public_url": "https://ceqanet.lci.ca.gov/",
            "record_categories": ["ceqa", "document"],
        }
    )


def _fixture_row() -> dict[str, str]:
    return {
        "sch_number": "2026000001",
        "title": "Synthetic Warehouse Project",
        "county": "San Bernardino",
        "lead_agency": "Synthetic Lead Agency",
        "document_type": "EIR",
        "received_date": "2026-01-15",
        "posted_date": "2026-01-16",
        "project_location": "Synthetic Project Location",
        "description": "Synthetic environmental review description.",
        "record_url": "https://ceqanet.lci.ca.gov/2026000001",
    }


def test_ceqanet_fixture_parser_normalizes_record() -> None:
    record = CeqanetFixtureParser().parse_row(
        _fixture_row(),
        source_name="CEQAnet State Clearinghouse",
        source_url="https://ceqanet.lci.ca.gov/",
    )

    assert record.ceqa_key == "ceqanet:sch:2026000001"
    assert record.title == "Synthetic Warehouse Project"
    assert record.county == "San Bernardino"
    assert record.lead_agency == "Synthetic Lead Agency"
    assert record.has_state_clearinghouse_number is True
    assert record.is_high_signal_document is True


def test_ceqanet_fixture_parser_preserves_provenance() -> None:
    record = CeqanetFixtureParser().parse_row(
        _fixture_row(),
        source_name="CEQAnet State Clearinghouse",
        source_url="https://ceqanet.lci.ca.gov/",
    )

    assert len(record.provenance) == 1
    assert record.provenance[0].source_name == "CEQAnet State Clearinghouse"
    assert str(record.provenance[0].source_url) == "https://ceqanet.lci.ca.gov/2026000001"
    assert record.provenance[0].adapter_family == "ceqanet"
    assert record.provenance[0].confidence_score == 85


def test_ceqanet_adapter_discovers_public_search_descriptor() -> None:
    adapter = CeqanetAdapter(_source())

    descriptors = adapter.discover_search()

    assert len(descriptors) == 1
    assert descriptors[0].search_name == "CEQAnet Advanced Search"
    assert descriptors[0].public_url == "https://ceqanet.lci.ca.gov/Search/Advanced"
    assert descriptors[0].record_types == ["ceqa", "document"]


def test_ceqanet_adapter_runs_fixture_rows_through_runner() -> None:
    adapter = CeqanetAdapter(_source(), fixture_rows=[_fixture_row()])

    result = AdapterRunner().run_adapter(adapter)

    assert result.succeeded is True
    assert len(result.records) == 1
    record = result.records[0]
    assert record.ceqa_key == "ceqanet:sch:2026000001"
    assert record.is_high_signal_document is True


def test_ceqanet_live_discovery_detects_public_search_fields() -> None:
    response = httpx.Response(
        status_code=200,
        request=httpx.Request("GET", CEQANET_ADVANCED_SEARCH_URL),
        text="Advanced Search SCH Number Document Type Received Date Lead Agency Public Agency",
    )
    discovery = CeqanetLiveDiscovery(client=MockCeqanetHttpClient(response=response))

    result = discovery.discover()

    assert result.reachable is True
    assert result.advanced_search_available is True
    assert result.sch_number_field_detected is True
    assert result.document_type_field_detected is True
    assert result.date_field_detected is True
    assert result.lead_agency_field_detected is True
    assert result.confidence_score == 95


def test_ceqanet_live_discovery_handles_http_error() -> None:
    discovery = CeqanetLiveDiscovery(
        client=MockCeqanetHttpClient(error=httpx.ConnectError("synthetic failure"))
    )

    result = discovery.discover()

    assert result.reachable is False
    assert result.advanced_search_available is False
    assert result.status_code is None
    assert result.confidence_score == 0
    assert result.notes == "HTTP request failed: ConnectError"
