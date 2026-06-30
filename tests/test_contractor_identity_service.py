from constructionsight.contractor_identity_models import (
    ContractorIdentityStatus,
    ContractorSourceKind,
)
from constructionsight.contractor_identity_service import (
    build_contractor_identity,
    normalize_contractor_license,
    normalize_contractor_name,
    resolve_contractor_identity,
)


def test_normalize_contractor_name_is_deterministic() -> None:
    assert normalize_contractor_name("  Acme-Builders, Inc. ") == "ACME BUILDERS INC"


def test_normalize_contractor_license_keeps_digits_only() -> None:
    assert normalize_contractor_license("LIC # 123-456") == "123456"


def test_build_contractor_identity_scores_active_license_highly() -> None:
    identity = build_contractor_identity(
        display_name="Acme Builders Inc.",
        source_kind=ContractorSourceKind.CSLB,
        license_number="123-456",
        license_status=ContractorIdentityStatus.ACTIVE,
        classification="B",
        contractor_group_key="contractor-group:acme",
        county="Riverside",
    )

    assert identity.contractor_key.startswith("contractor:")
    assert identity.normalized_name == "ACME BUILDERS INC"
    assert identity.license is not None
    assert identity.license.license_number == "123456"
    assert identity.confidence_score == 100
    assert "contractor license status is active" in identity.reasons


def test_build_contractor_identity_without_license_preserves_limitation() -> None:
    identity = build_contractor_identity(display_name="Acme Builders")

    assert identity.confidence_score == 35
    assert "no contractor license signal was available" in identity.limitations


def test_resolve_contractor_identity_returns_unresolved_for_no_candidates() -> None:
    resolution = resolve_contractor_identity([])

    assert resolution.status == "unresolved"
    assert resolution.candidates == []
    assert resolution.limitations == ["no contractor identity candidates provided"]


def test_resolve_contractor_identity_selects_highest_score() -> None:
    weak = build_contractor_identity(display_name="Acme Builders")
    strong = build_contractor_identity(
        display_name="Acme Builders",
        license_number="123456",
        license_status=ContractorIdentityStatus.ACTIVE,
    )

    resolution = resolve_contractor_identity([weak, strong])

    assert resolution.status == "resolved"
    assert resolution.primary_contractor_key == strong.contractor_key


def test_resolve_contractor_identity_preserves_ambiguity() -> None:
    first = build_contractor_identity(display_name="Acme Builders")
    second = build_contractor_identity(display_name="Acme Builders LLC")

    resolution = resolve_contractor_identity([first, second])

    assert resolution.status == "ambiguous"
    assert resolution.primary_contractor_key is None
    assert resolution.limitations == ["multiple contractor candidates tied"]
