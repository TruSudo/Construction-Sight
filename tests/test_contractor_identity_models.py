import pytest
from pydantic import ValidationError

from constructionsight.contractor_identity_models import (
    ContractorIdentity,
    ContractorIdentityResolution,
    ContractorIdentityStatus,
    ContractorLicense,
)
from constructionsight.domain_types import confidence_band


def test_contractor_license_normalizes_number() -> None:
    license_signal = ContractorLicense(
        license_number=" 123 456 ",
        status=ContractorIdentityStatus.ACTIVE,
    )

    assert license_signal.license_number == "123456"


def test_contractor_license_rejects_blank_number() -> None:
    with pytest.raises(ValidationError):
        ContractorLicense(license_number="   ")


def test_contractor_identity_requires_matching_confidence_band() -> None:
    with pytest.raises(ValidationError):
        ContractorIdentity(
            contractor_key="contractor:test",
            display_name="Example Builder",
            normalized_name="EXAMPLE BUILDER",
            confidence_score=90,
            confidence_band=confidence_band(10),
        )


def test_contractor_identity_serializes_to_dict() -> None:
    identity = ContractorIdentity(
        contractor_key="contractor:test",
        display_name="Example Builder",
        normalized_name="EXAMPLE BUILDER",
        confidence_score=80,
        confidence_band=confidence_band(80),
        reasons=["contractor name is present"],
    )

    payload = identity.to_dict()

    assert payload["contractor_key"] == "contractor:test"
    assert payload["confidence_score"] == 80


def test_contractor_resolution_requires_primary_candidate() -> None:
    with pytest.raises(ValidationError):
        ContractorIdentityResolution(
            resolution_id="contractor-resolution:test",
            status="resolved",
            primary_contractor_key="contractor:missing",
            candidates=[],
        )


def test_contractor_resolution_serializes() -> None:
    identity = ContractorIdentity(
        contractor_key="contractor:test",
        display_name="Example Builder",
        normalized_name="EXAMPLE BUILDER",
        confidence_score=35,
        confidence_band=confidence_band(35),
    )
    resolution = ContractorIdentityResolution(
        resolution_id="contractor-resolution:test",
        status="resolved",
        primary_contractor_key="contractor:test",
        candidates=[identity],
    )

    assert resolution.to_dict()["status"] == "resolved"
