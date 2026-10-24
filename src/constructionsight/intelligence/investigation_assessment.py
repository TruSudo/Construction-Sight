"""Read-only evidence analysis for the canonical cross-source investigation dossier.

Variations in parcel, address or county claims are review questions, not proof
of contradiction or project identity. The projection creates no source facts,
relationships, permissions, network requests, or independent intelligence store.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import pairwise
from typing import Any

from constructionsight.intelligence.artifact_identity import (
    IdentityArtifactType,
    normalize_artifact_value,
)
from constructionsight.intelligence.investigation_service import InvestigationObservation

_LOCATION_FIELDS = (
    ("county", None),
    ("apn", IdentityArtifactType.APN),
    ("exact_site_address", IdentityArtifactType.EXACT_SITE_ADDRESS),
)
_PARTY_ROLES = ("owner", "developer", "general_contractor")
_MAX_FINDINGS = 100
_MAX_CLAIM_REFERENCES = 100


def _values(observation: InvestigationObservation, field: str) -> list[str]:
    if field == "title":
        return [observation.title] if observation.title else []
    if field == "county":
        return [observation.county] if observation.county else []
    kind = IdentityArtifactType(field)
    return observation.artifacts.get(kind, [])


def _normalize(field: str, raw: str) -> str:
    if field == "title":
        return " ".join(raw.casefold().split())
    if field == "county":
        return raw.strip().casefold().removesuffix(" county")
    return normalize_artifact_value(IdentityArtifactType(field), raw)


def _history_values(payload: dict[str, Any], field: str) -> tuple[str, ...]:
    if field == "title":
        value = payload.get("title")
        return (value.strip().casefold(),) if isinstance(value, str) and value.strip() else ()
    if field == "county":
        value = payload.get("county")
        raw = [value] if isinstance(value, str) and value.strip() else []
    else:
        artifacts = payload.get("artifacts", {})
        value = artifacts.get(field, []) if isinstance(artifacts, dict) else []
        raw = [x for x in value if isinstance(x, str) and x.strip()]
    return tuple(sorted({_normalize(field, x) for x in raw}))


def assess_investigation_evidence(
    current: list[InvestigationObservation],
    chronology: list[dict[str, Any]],
    *,
    candidate_links: list[dict[str, Any]],
    pending_association_reviews: list[str],
    source_parties: list[dict[str, Any]],
    source_history_truncated: bool,
    relationship_contradictions: int,
) -> dict[str, Any]:
    """Assess retained claims; never convert diversity into a verified conflict."""
    discrepancies: list[dict[str, Any]] = []
    claims_truncated = False
    for field, _ in (*_LOCATION_FIELDS, ("title", None)):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for observation in current:
            for raw in sorted(set(_values(observation, field))):
                normalized = _normalize(field, raw)
                groups[normalized].append(
                    {
                        "source_id": observation.source_entity_id,
                        "source_family": observation.evidence.source_family,
                        "source_record_id": observation.evidence.source_record_id,
                        "evidence_id": observation.evidence.evidence_id,
                        "source_claim": raw,
                    }
                )
        unique_sources = {
            entry["source_id"] for entries in groups.values() for entry in entries
        }
        if len(groups) < 2 or len(unique_sources) < 2:
            continue
        # Different parcels or addresses may both be correct for a multi-site
        # project. Even a county difference is a question, not a finding of error.
        references = [
            (value, item)
            for value, entries in sorted(groups.items())
            for item in sorted(
                entries, key=lambda entry: (entry["source_id"], entry["source_claim"])
            )
        ]
        if len(references) > _MAX_CLAIM_REFERENCES:
            claims_truncated = True
        shown: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for value, item in references[:_MAX_CLAIM_REFERENCES]:
            shown[value].append(item)
        discrepancies.append(
            {
                "field": field,
                "classification": "source_claim_variation_requires_review",
                "claims": [
                    {"normalized_claim": value, "sources": entries}
                    for value, entries in sorted(shown.items())
                ],
                "claims_truncated": len(references) > _MAX_CLAIM_REFERENCES,
                "potentially_valid_multi_location": field in {"apn", "exact_site_address"},
                "potentially_valid_alias": field == "title",
                "independently_verified_contradiction": False,
                "requires_review": True,
            }
        )

    party_variations: list[dict[str, Any]] = []
    for role in _PARTY_ROLES:
        claims: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for observation in current:
            for party in observation.parties:
                if party.role.value != role:
                    continue
                canonical = " ".join(party.name.casefold().split())
                claims[canonical].append(
                    {
                        "name": party.name,
                        "source_id": observation.source_entity_id,
                        "evidence_id": observation.evidence.evidence_id,
                        "entity_key": party.entity_key,
                    }
                )
        source_ids = {
            claim["source_id"] for values in claims.values() for claim in values
        }
        if len(claims) < 2 or len(source_ids) < 2:
            continue
        flattened = [
            (name, item)
            for name, entries in sorted(claims.items())
            for item in sorted(entries, key=lambda item: (item["source_id"], item["name"]))
        ]
        if len(flattened) > _MAX_CLAIM_REFERENCES:
            claims_truncated = True
        shown_parties: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for name, item in flattened[:_MAX_CLAIM_REFERENCES]:
            shown_parties[name].append(item)
        party_variations.append(
            {
                "role": role,
                "source_claims": [
                    {"normalized_name": name, "evidence": entries}
                    for name, entries in sorted(shown_parties.items())
                ],
                "claims_truncated": len(flattened) > _MAX_CLAIM_REFERENCES,
                "classification": "unresolved_source_claimed_party_variation",
                "independently_verified_entity_conflict": False,
                "requires_review": True,
            }
        )

    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in chronology:
        by_source[event["source_id"]].append(event)
    revisions: list[dict[str, Any]] = []
    revision_truncated = False
    for source_id, events in sorted(by_source.items()):
        for previous, following in pairwise(events):
            for field, _ in (*_LOCATION_FIELDS, ("title", None)):
                before = _history_values(previous["observation"], field)
                after = _history_values(following["observation"], field)
                if before == after:
                    continue
                if len(revisions) >= _MAX_FINDINGS:
                    revision_truncated = True
                    break
                revisions.append(
                    {
                        "source_id": source_id,
                        "field": field,
                        "previous_claims": list(before),
                        "subsequent_claims": list(after),
                        "previous_evidence_id": previous["evidence_id"],
                        "subsequent_evidence_id": following["evidence_id"],
                        "subsequent_effective_at": following["effective_at"],
                        "classification": "historical_source_claim_change",
                        "independently_verified_contradiction": False,
                    }
                )
            if revision_truncated:
                break
        if revision_truncated:
            break

    families = {observation.evidence.source_family for observation in current}
    gaps: list[dict[str, str]] = []

    def gap(code: str, detail: str) -> None:
        gaps.append({"code": code, "detail": detail, "state": "unresolved"})

    gap("identity_verification", "Retained source association does not verify project identity.")
    gap("commercial_authority", "No authorization to contact, bid or represent a buyer is proven.")
    gap("physical_activity", "Current on-site construction activity is not independently verified.")
    if len(families) < 2:
        gap("multi_source_membership", "A second source family has not joined this investigation.")
    for family in ("permit", "planning", "ceqa", "parcel"):
        if family not in families:
            gap(
                "retained_" + family + "_coverage",
                "No " + family + " record is present in this retained investigation; "
                "this does not establish that such records do not exist.",
            )
    if not any(observation.latitude is not None for observation in current):
        gap("mappable_coordinates", "No retained complete coordinate pair for map placement.")
    if not any(
        observation.artifacts.get(IdentityArtifactType.APN) for observation in current
    ):
        gap("parcel_anchor", "No retained APN claim supports a parcel-backed site assessment.")
    predicates = {
        item["relationship"]["predicate"]
        for item in source_parties
        if isinstance(item.get("relationship"), dict)
    }
    if not any(
        value in predicates
        for value in ("source_claimed_contractor", "source_claimed_general_contractor")
    ):
        gap("contractor_evidence", "No source-claimed contractor is present in this dossier.")
    if not any(
        value in predicates
        for value in ("source_claimed_owner", "source_claimed_developer")
    ):
        gap("owner_developer_evidence", "No source-claimed owner or developer is present.")
    if discrepancies:
        gap(
            "source_claim_variations",
            "Different current location or project-title claims require source review.",
        )
    if party_variations:
        gap(
            "source_party_variations",
            "Different source-claimed owner, developer or GC names need identity review.",
        )
    if relationship_contradictions:
        gap("relationship_conflicts", "Retained graph conflict evidence requires human assessment.")
    if any(link["contradictory_evidence_ids"] for link in candidate_links):
        gap(
            "candidate_conflicts",
            "Potential cross-investigation links contain conflicting evidence.",
        )
    if candidate_links:
        gap("identity_candidates", "Unreviewed cross-investigation candidates remain separate.")
    if pending_association_reviews:
        gap(
            "association_reassessment",
            "A reviewed association predates changed retained evidence.",
        )
    if source_history_truncated or revision_truncated:
        gap("bounded_history", "The current evidence page does not show complete source history.")
    if claims_truncated:
        gap("bounded_claims", "The source-claim review preview exceeds its bounded evidence page.")

    return {
        "schema_version": "constructionsight.investigation-evidence-assessment/v1",
        "source_claim_discrepancies": discrepancies,
        "source_party_variations": party_variations,
        "source_claim_discrepancies_truncated": claims_truncated,
        "source_revision_changes": revisions,
        "source_revision_changes_truncated": revision_truncated,
        "information_gaps": gaps,
        "human_review_required": bool(
            discrepancies
            or party_variations
            or relationship_contradictions
            or candidate_links
            or pending_association_reviews
            or revision_truncated
            or claims_truncated
        ),
        "independently_verified_project_identity": False,
        "commercial_authority_granted": False,
    }
