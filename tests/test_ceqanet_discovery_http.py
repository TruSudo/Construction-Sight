from __future__ import annotations

import inspect

import pytest

import constructionsight.ceqanet_discovery_http as discovery_http
from constructionsight.ceqanet_discovery_http import CeqanetLiveDiscovery
from constructionsight.ceqanet_endpoints import CEQANET_ADVANCED_SEARCH_URL
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
)


def _observation(
    *,
    failure_kind: HttpFailureKind = HttpFailureKind.NONE,
    status_code: int | None = 200,
    body: bytes = (
        b"Advanced Search SCH Number Document Type Date Lead Agency"
    ),
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
        error_type=None,
        error_detail=None,
    )


def test_live_discovery_does_not_accept_caller_selected_executor() -> None:
    parameters = inspect.signature(CeqanetLiveDiscovery).parameters

    assert "executor" not in parameters


def test_live_discovery_uses_owned_http_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, BoundedHttpPolicy]] = []

    def owned_test_effect(
        url: str,
        method: str,
        policy: BoundedHttpPolicy,
    ) -> BoundedHttpObservation:
        calls.append((url, method, policy))
        return _observation()

    monkeypatch.setattr(discovery_http, "_execute_bounded_http", owned_test_effect)

    result = CeqanetLiveDiscovery(timeout_seconds=7.5).discover()

    assert len(calls) == 1
    url, method, policy = calls[0]
    assert url == CEQANET_ADVANCED_SEARCH_URL
    assert method == "GET"
    assert policy.policy_id == "CS-NET-001"
    assert policy.read_timeout_seconds == 7.5
    assert result.reachable is True
    assert result.advanced_search_available is True
    assert result.sch_number_field_detected is True
    assert result.document_type_field_detected is True
    assert result.date_field_detected is True
    assert result.lead_agency_field_detected is True
    assert result.failure_kind is HttpFailureKind.NONE


def test_live_discovery_preserves_fail_closed_transport_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def denied_test_effect(
        _url: str,
        _method: str,
        _policy: BoundedHttpPolicy,
    ) -> BoundedHttpObservation:
        return _observation(
            failure_kind=HttpFailureKind.ACCESS_CONTROL,
            status_code=403,
            body=b"denied",
        )

    monkeypatch.setattr(discovery_http, "_execute_bounded_http", denied_test_effect)

    result = CeqanetLiveDiscovery().discover()

    assert result.reachable is True
    assert result.status_code == 403
    assert result.advanced_search_available is False
    assert result.sch_number_field_detected is False
    assert result.document_type_field_detected is False
    assert result.date_field_detected is False
    assert result.lead_agency_field_detected is False
    assert result.failure_kind is HttpFailureKind.ACCESS_CONTROL
    assert result.notes == "CEQAnet discovery failed closed: access_control"
