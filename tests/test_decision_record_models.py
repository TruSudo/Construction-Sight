import pytest
from pydantic import ValidationError

from constructionsight.decision_record_models import (
    DecisionKind,
    DecisionMatchStatus,
    DecisionRecord,
    DecisionSiteMatch,
    DecisionSourceKind,
)
from constructionsight.domain_types import confidence_band


def test_decision_record_requires_matching_confidence_band() -> None:
    with pytest.raises(ValidationError):
        DecisionRecord(
            decision_key="decision:test",
            source_key="test:source",
            source_kind=DecisionSourceKind.AGENDA,
            decision_kind=DecisionKind.HEARING,
            title="Project hearing",
            normalized_title="PROJECT HEARING",
            confidence_score=90,
            confidence_band=confidence_band(10),
        )


def test_decision_record_rejects_duplicate_limitations() -> None:
    with pytest.raises(ValidationError):
        DecisionRecord(
            decision_key="decision:test",
            source_key="test:source",
            title="Project hearing",
            normalized_title="PROJECT HEARING",
            limitations=["x", "x"],
        )


def test_decision_record_serializes_to_dict() -> None:
    decision = DecisionRecord(
        decision_key="decision:test",
        source_key="test:source",
        source_kind=DecisionSourceKind.STAFF_REPORT,
        decision_kind=DecisionKind.APPROVAL,
        title="Project approval",
        normalized_title="PROJECT APPROVAL",
        confidence_score=80,
        confidence_band=confidence_band(80),
    )

    assert decision.to_dict()["decision_kind"] == "approval"


def test_matched_decision_site_match_requires_site_key() -> None:
    with pytest.raises(ValidationError):
        DecisionSiteMatch(
            decision_key="decision:test",
            status=DecisionMatchStatus.MATCHED,
            confidence_score=90,
            confidence_band=confidence_band(90),
        )


def test_decision_site_match_requires_matching_confidence_band() -> None:
    with pytest.raises(ValidationError):
        DecisionSiteMatch(
            decision_key="decision:test",
            site_key="site:test",
            status=DecisionMatchStatus.MATCHED,
            confidence_score=90,
            confidence_band=confidence_band(10),
        )


def test_decision_site_match_serializes_to_dict() -> None:
    match = DecisionSiteMatch(
        decision_key="decision:test",
        site_key="site:test",
        status=DecisionMatchStatus.MATCHED,
        confidence_score=70,
        confidence_band=confidence_band(70),
    )

    assert match.to_dict()["status"] == "matched"
