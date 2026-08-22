import constructionsight.adapters.ceqanet as ceqanet_adapter_module
from constructionsight.adapters.ceqanet import (
    CEQANET_ADVANCED_SEARCH_URL,
    CeqanetAdapter,
    CeqanetFixtureParser,
    CeqanetLiveDiscovery,
)
from constructionsight.adapters.runner import AdapterRunner
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
)
from constructionsight.models import PublicSource


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


def _observation(
    *,
    body: bytes = b"",
    status_code: int | None = 200,
    failure_kind: HttpFailureKind = HttpFailureKind.NONE,
    error_type: str | None = None,
) -> BoundedHttpObservation:
    return BoundedHttpObservation(
        policy_id="CS-NET-001",
        method="GET",
        request_url=CEQANET_ADVANCED_SEARCH_URL,
        final_url=CEQANET_ADVANCED_SEARCH_URL,
        status_code=status_code,
        content_type="text/html" if status_code is not None else None,
        content_encoding="utf-8" if status_code is not None else None,
        response_body=body,
        response_size=len(body),
        body_truncated=False,
        failure_kind=failure_kind,
        error_type=error_type,
        error_detail=None,
    )


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
    assert descriptors[0].public_url == CEQANET_ADVANCED_SEARCH_URL
    assert descriptors[0].record_types == ["ceqa", "document"]


def test_ceqanet_adapter_runs_fixture_rows_through_runner() -> None:
    adapter = CeqanetAdapter(_source(), fixture_rows=[_fixture_row()])

    result = AdapterRunner().run_adapter(adapter)

    assert result.succeeded is True
    assert len(result.records) == 1
    record = result.records[0]
    assert record.ceqa_key == "ceqanet:sch:2026000001"
    assert record.is_high_signal_document is True


def test_ceqanet_adapter_namespace_does_not_reexport_live_transport() -> None:
    assert not hasattr(ceqanet_adapter_module, "CeqanetLiveDiscovery")
    assert not hasattr(ceqanet_adapter_module, "CeqanetDiscoveryResult")
    assert "CeqanetLiveDiscovery" not in ceqanet_adapter_module.__all__
    assert "CeqanetDiscoveryResult" not in ceqanet_adapter_module.__all__


def test_ceqanet_live_discovery_detects_public_search_fields() -> None:
    body = b"Advanced Search SCH Number Document Type Received Date Lead Agency Public Agency"

    def executor(
        url: str,
        method: str,
        policy: BoundedHttpPolicy,
    ) -> BoundedHttpObservation:
        assert url == CEQANET_ADVANCED_SEARCH_URL
        assert method == "GET"
        assert policy.policy_id == "CS-NET-001"
        assert policy.max_response_bytes == 50_000
        return _observation(body=body)

    discovery = CeqanetLiveDiscovery(executor=executor)

    result = discovery.discover()

    assert result.reachable is True
    assert result.advanced_search_available is True
    assert result.sch_number_field_detected is True
    assert result.document_type_field_detected is True
    assert result.date_field_detected is True
    assert result.lead_agency_field_detected is True
    assert result.confidence_score == 95
    assert result.failure_kind is HttpFailureKind.NONE


def test_ceqanet_live_discovery_preserves_transport_failure_class() -> None:
    def executor(
        url: str,
        method: str,
        policy: BoundedHttpPolicy,
    ) -> BoundedHttpObservation:
        return _observation(
            status_code=None,
            failure_kind=HttpFailureKind.TRANSPORT,
            error_type="ConnectError",
        )

    discovery = CeqanetLiveDiscovery(executor=executor)

    result = discovery.discover()

    assert result.reachable is False
    assert result.advanced_search_available is False
    assert result.status_code is None
    assert result.confidence_score == 0
    assert result.failure_kind is HttpFailureKind.TRANSPORT
    assert result.notes == "CEQAnet discovery failed closed: transport_failure"
