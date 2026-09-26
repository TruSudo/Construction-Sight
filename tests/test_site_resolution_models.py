import pytest
from pydantic import ValidationError

from constructionsight.domain_types import ConfidenceBand
from constructionsight.site_resolution_models import (
    GeometryHint,
    GeometryHintKind,
    SiteIdentifier,
    SiteIdentifierKind,
    SiteMatchStrength,
    SiteResolutionCandidate,
    SiteResolutionInput,
    SiteResolutionResult,
    SiteResolutionStatus,
)


def test_site_resolution_input_rejects_duplicate_identifiers() -> None:
    identifier = SiteIdentifier(
        identifier_kind=SiteIdentifierKind.APN,
        value="123-456-78",
        normalized_value="12345678",
        evidence_id="evidence:test",
    )

    with pytest.raises(ValidationError):
        SiteResolutionInput(
            source_name="test source",
            identifiers=[identifier, identifier],
        )


def test_geometry_hint_requires_coordinates_for_point() -> None:
    with pytest.raises(ValidationError):
        GeometryHint(
            geometry_kind=GeometryHintKind.POINT,
            source_name="test source",
            evidence_id="evidence:test",
        )


def test_candidate_requires_matching_confidence_band() -> None:
    with pytest.raises(ValidationError):
        SiteResolutionCandidate(
            site_key="site:abc",
            match_strength=SiteMatchStrength.STRONG,
            confidence_score=90,
            confidence_band=ConfidenceBand.LOW,
        )


def test_result_model_rejects_unresolved_with_candidate() -> None:
    candidate = SiteResolutionCandidate(
        site_key="site:abc",
        match_strength=SiteMatchStrength.STRONG,
        confidence_score=90,
        confidence_band=ConfidenceBand.HIGH,
    )

    with pytest.raises(ValidationError):
        SiteResolutionResult(
            resolution_id="site-resolution:abc",
            source_name="test source",
            status=SiteResolutionStatus.UNRESOLVED,
            candidates=[candidate],
        )
