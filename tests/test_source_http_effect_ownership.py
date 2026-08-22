from __future__ import annotations

import inspect

from constructionsight.models import (
    Jurisdiction,
    PlatformFamily,
    PublicSource,
    SourceType,
    VerificationStatus,
)
from constructionsight.source_readiness_http import check_source_http_reachability
from constructionsight.source_verification_http import source_verification_policy


def _source() -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="Test City",
            county="San Bernardino",
            jurisdiction_type="city",
        ),
        source_name="Test Source",
        source_type=SourceType.CITY_PORTAL,
        platform_family=PlatformFamily.ACCELA_ACA,
        public_url="https://example.invalid/source",
        verification_status=VerificationStatus.UNVERIFIED,
    )


def test_source_readiness_transport_does_not_accept_caller_selected_executor() -> None:
    assert "executor" not in inspect.signature(
        check_source_http_reachability
    ).parameters


def test_source_verification_policy_is_exact_get_only_authority() -> None:
    policy = source_verification_policy(_source(), timeout_seconds=10.0)

    assert policy.policy_id == "CS-NET-008"
    assert policy.allowed_methods == ("GET",)
    assert policy.max_response_bytes == 50_000
    assert policy.allowed_request_urls == ("https://example.invalid/source",)
