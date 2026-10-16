"""Contract checks for bounded source-backed investigation assessment.

Synthetic claims here are not evidence of real jurisdictional project activity.
"""

from datetime import UTC, datetime, timedelta

from constructionsight.domain_types import PartyRole
from constructionsight.entity_models import Entity
from constructionsight.intelligence.artifact_identity import IdentityArtifactType as Artifact
from constructionsight.intelligence.investigation_assessment import (
    assess_investigation_evidence,
)
from constructionsight.intelligence.investigation_service import InvestigationObservation
from constructionsight.intelligence.schemas import EvidenceRecord

AT = datetime(2026, 10, 16, tzinfo=UTC)


def source(
    family: str,
    *,
    county: str = "Riverside",
    apns: list[str] | None = None,
    address: str | None = None,
    day: int = 0,
    title: str | None = None,
    parties: list[Entity] | None = None,
) -> InvestigationObservation:
    artifacts: dict[Artifact, list[str]] = {}
    if apns:
        artifacts[Artifact.APN] = apns
    if address:
        artifacts[Artifact.EXACT_SITE_ADDRESS] = [address]
    return InvestigationObservation(
        evidence=EvidenceRecord(
            evidence_id=f"evidence:synthetic:{family}:{day}",
            source_name=f"Synthetic {family}",
            source_family=family,
            source_record_id=f"{family}:1",
            record_type=family,
            retrieved_at=AT + timedelta(days=day),
            observed_at=AT + timedelta(days=day),
            raw_observations={"synthetic": True},
        ),
        title=title,
        county=county,
        artifacts=artifacts,
        parties=parties or [],
    )


def assess(
    observations: list[InvestigationObservation],
    chronology: list[dict] | None = None,
    *,
    candidates: list[dict] | None = None,
    pending: list[str] | None = None,
    conflict_count: int = 0,
    truncated: bool = False,
) -> dict:
    return assess_investigation_evidence(
        observations,
        chronology or [],
        candidate_links=candidates or [],
        pending_association_reviews=pending or [],
        source_parties=[],
        source_history_truncated=truncated,
        relationship_contradictions=conflict_count,
    )


def test_different_current_apns_and_addresses_remain_review_questions_not_verified_conflicts():
    left = source("ceqa", apns=["123-456"], address="123 Main St")
    right = source("permit", apns=["999-888"], address="900 Industrial Blvd")
    report = assess([left, right])
    fields = {item["field"] for item in report["source_claim_discrepancies"]}
    assert fields == {"apn", "exact_site_address"}
    for item in report["source_claim_discrepancies"]:
        assert item["classification"] == "source_claim_variation_requires_review"
        assert item["independently_verified_contradiction"] is False
        assert item["potentially_valid_multi_location"]
        assert {entry["evidence_id"] for claim in item["claims"] for entry in claim["sources"]} == {
            left.evidence.evidence_id,
            right.evidence.evidence_id,
        }
    assert report["human_review_required"] is True
    assert report["independently_verified_project_identity"] is False
    assert report["commercial_authority_granted"] is False
    codes = {item["code"] for item in report["information_gaps"]}
    assert "source_claim_variations" in codes
    assert "physical_activity" in codes
    assert "retained_planning_coverage" in codes
    assert "retained_parcel_coverage" in codes
    assert "contractor_evidence" in codes


def test_equivalent_counties_and_same_parcel_do_not_invent_discrepancies():
    left = source("ceqa", county="Riverside County", apns=["123-456"])
    right = source("permit", county="riverside", apns=["123-456"])
    report = assess([left, right])
    assert report["source_claim_discrepancies"] == []
    assert report["human_review_required"] is False
    assert all(item["code"] != "source_claim_variations" for item in report["information_gaps"])


def test_multiple_parcels_in_one_source_are_not_a_cross_source_conflict():
    record = source("planning", apns=["123", "456"])
    report = assess([record])
    assert report["source_claim_discrepancies"] == []
    assert {x["code"] for x in report["information_gaps"]} >= {"multi_source_membership"}


def test_revised_source_title_and_apn_are_attributed_to_exact_retained_evidence():
    earlier = source("permit", apns=["123"], title="Proposed building")
    current = source("permit", apns=["456"], day=2, title="Revised building")
    assert earlier.source_entity_id == current.source_entity_id
    chronology = [
        {
            "source_id": item.source_entity_id,
            "evidence_id": item.evidence.evidence_id,
            "effective_at": item.effective_at.isoformat(),
            "observation": item.model_dump(mode="json", round_trip=True),
        }
        for item in (earlier, current)
    ]
    report = assess([current], chronology, pending=["relationship:review"])
    changes = report["source_revision_changes"]
    assert {item["field"] for item in changes} == {"apn", "title"}
    assert all(item["source_id"] == earlier.source_entity_id for item in changes)
    assert all(
        item["previous_evidence_id"] == earlier.evidence.evidence_id
        and item["subsequent_evidence_id"] == current.evidence.evidence_id
        and item["independently_verified_contradiction"] is False
        for item in changes
    )
    assert any(gap["code"] == "association_reassessment" for gap in report["information_gaps"])


def test_known_relationship_conflicts_and_candidate_conflicts_do_not_upgrade_identity():
    record = source("ceqa")
    report = assess(
        [record],
        candidates=[{"contradictory_evidence_ids": ["evidence:other"]}],
        conflict_count=1,
    )
    assert {"relationship_conflicts", "candidate_conflicts", "identity_candidates"} <= {
        item["code"] for item in report["information_gaps"]
    }
    assert report["independently_verified_project_identity"] is False
    assert report["commercial_authority_granted"] is False


def test_claim_preview_is_bounded_without_discarding_review_warning():
    left = source("ceqa", apns=[f"123-{n:03d}" for n in range(90)])
    right = source("permit", apns=[f"456-{n:03d}" for n in range(90)])
    report = assess([left, right], truncated=True)
    assert report["source_claim_discrepancies_truncated"] is True
    discrepancy = next(
        item for item in report["source_claim_discrepancies"] if item["field"] == "apn"
    )
    assert discrepancy["claims_truncated"] is True
    assert sum(len(claim["sources"]) for claim in discrepancy["claims"]) == 100
    assert {"bounded_history", "bounded_claims"} <= {
        item["code"] for item in report["information_gaps"]
    }


def test_unreconciled_titles_and_owner_names_are_evidence_claims_not_identity_proof():
    left = source(
        "ceqa",
        apns=["123"],
        title="Warehouse development",
        parties=[Entity(entity_key="ceqa-owner", name="Acme Land LLC", role=PartyRole.OWNER)],
    )
    right = source(
        "planning",
        apns=["123"],
        title="Logistics park",
        parties=[Entity(entity_key="planning-owner", name="Acme Holdings", role=PartyRole.OWNER)],
    )
    report = assess([left, right])
    title = next(
        item for item in report["source_claim_discrepancies"] if item["field"] == "title"
    )
    assert title["potentially_valid_alias"] is True
    assert title["independently_verified_contradiction"] is False
    owners = report["source_party_variations"]
    assert len(owners) == 1
    assert owners[0]["role"] == "owner"
    assert owners[0]["independently_verified_entity_conflict"] is False
    assert {
        item["evidence_id"]
        for claim in owners[0]["source_claims"]
        for item in claim["evidence"]
    } == {left.evidence.evidence_id, right.evidence.evidence_id}
    assert {"source_party_variations", "source_claim_variations"} <= {
        gap["code"] for gap in report["information_gaps"]
    }
    assert report["independently_verified_project_identity"] is False
