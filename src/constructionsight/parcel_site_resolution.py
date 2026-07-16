"""Parcel-backed site resolution helpers."""

from __future__ import annotations

import hashlib

from constructionsight.domain_types import confidence_band
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_topology import (
    ParcelPointContainment,
    evaluate_parcel_point_containment,
)
from constructionsight.site_resolution_models import (
    GeometryHint,
    SiteIdentifier,
    SiteIdentifierKind,
    SiteMatchStrength,
    SiteResolutionCandidate,
    SiteResolutionInput,
    SiteResolutionResult,
    SiteResolutionStatus,
)
from constructionsight.site_resolution_service import resolve_site

ParcelMatch = tuple[ParcelCoreRecord, int, list[str], list[str]]


def resolve_site_with_parcels(
    site_input: SiteResolutionInput,
    parcels: list[ParcelCoreRecord],
) -> SiteResolutionResult:
    """Resolve a site using parcel core records when possible."""

    matches = _match_parcels(site_input, parcels)
    if not matches:
        fallback = resolve_site(site_input)
        fallback.limitations.append("no parcel core record matched site signals")
        fallback.limitations = _unique(fallback.limitations)
        return fallback

    top_score = matches[0][1]
    top_matches = [match for match in matches if match[1] == top_score]
    candidates = [
        _candidate_from_parcel(
            site_input=site_input,
            parcel=parcel,
            score=score,
            reasons=reasons,
            match_limitations=match_limitations,
        )
        for parcel, score, reasons, match_limitations in top_matches
    ]
    status = (
        SiteResolutionStatus.RESOLVED if len(candidates) == 1 else SiteResolutionStatus.AMBIGUOUS
    )
    limitations = [] if len(candidates) == 1 else ["multiple parcel records matched equally"]
    primary_site_key = candidates[0].site_key if len(candidates) == 1 else None
    return SiteResolutionResult(
        resolution_id=_resolution_id(site_input, candidates),
        source_name=site_input.source_name,
        evidence_id=site_input.evidence_id,
        status=status,
        primary_site_key=primary_site_key,
        candidates=candidates,
        limitations=limitations,
    )


def _match_parcels(
    site_input: SiteResolutionInput,
    parcels: list[ParcelCoreRecord],
) -> list[ParcelMatch]:
    """Return parcel matches sorted by confidence score."""

    apn = _identifier_value(site_input.identifiers, SiteIdentifierKind.APN)
    address = _identifier_value(site_input.identifiers, SiteIdentifierKind.ADDRESS)
    matches: list[ParcelMatch] = []
    for parcel in parcels:
        score = 0
        reasons: list[str] = []
        match_limitations: list[str] = []
        if apn and parcel.normalized_apn == apn:
            score += 70
            reasons.append("APN matched parcel core record")
        if address and parcel.normalized_address == address:
            score += 20
            reasons.append("address matched parcel core record")
        containment = _point_hits_parcel(site_input.geometry_hints, parcel)
        if containment is not None:
            score += 10
            if containment.reason is not None:
                reasons.append(containment.reason)
            match_limitations.extend(containment.limitations)
        if score:
            matches.append(
                (
                    parcel,
                    min(score, 100),
                    _unique(reasons),
                    _unique(match_limitations),
                )
            )
    return sorted(matches, key=lambda match: (-match[1], match[0].parcel_record_id))


def _candidate_from_parcel(
    *,
    site_input: SiteResolutionInput,
    parcel: ParcelCoreRecord,
    score: int,
    reasons: list[str],
    match_limitations: list[str],
) -> SiteResolutionCandidate:
    """Build a site candidate from one matched parcel."""

    centroid_latitude = parcel.geometry.centroid_latitude if parcel.geometry else None
    centroid_longitude = parcel.geometry.centroid_longitude if parcel.geometry else None
    limitations = list(parcel.limitations)
    limitations.extend(match_limitations)
    if parcel.geometry is None:
        limitations.append("matched parcel does not include geometry")
    else:
        limitations.extend(parcel.geometry.limitations)
    return SiteResolutionCandidate(
        site_key=_site_key_from_parcel(parcel),
        match_strength=_match_strength(score),
        confidence_score=score,
        confidence_band=confidence_band(score),
        county=parcel.county,
        state=parcel.state,
        jurisdiction=parcel.jurisdiction,
        apn=parcel.normalized_apn,
        address=parcel.normalized_address,
        latitude=centroid_latitude,
        longitude=centroid_longitude,
        supporting_identifiers=site_input.identifiers,
        geometry_hints=site_input.geometry_hints,
        reasons=_unique(reasons),
        limitations=_unique(limitations),
    )


def _point_hits_parcel(
    geometry_hints: list[GeometryHint],
    parcel: ParcelCoreRecord,
) -> ParcelPointContainment | None:
    """Return the first coordinate hint contained by parcel geometry."""

    if parcel.geometry is None:
        return None
    for hint in geometry_hints:
        if hint.latitude is None or hint.longitude is None:
            continue
        containment = evaluate_parcel_point_containment(
            parcel.geometry,
            latitude=hint.latitude,
            longitude=hint.longitude,
        )
        if containment.contained:
            return containment
    return None


def _identifier_value(
    identifiers: list[SiteIdentifier],
    identifier_kind: SiteIdentifierKind,
) -> str | None:
    """Return first normalized identifier value for a kind."""

    for identifier in identifiers:
        if identifier.identifier_kind == identifier_kind:
            return identifier.normalized_value
    return None


def _match_strength(score: int) -> SiteMatchStrength:
    """Return match strength for a parcel-backed score."""

    if score >= 90:
        return SiteMatchStrength.EXACT
    if score >= 70:
        return SiteMatchStrength.STRONG
    if score >= 50:
        return SiteMatchStrength.MODERATE
    if score > 0:
        return SiteMatchStrength.WEAK
    return SiteMatchStrength.NONE


def _site_key_from_parcel(parcel: ParcelCoreRecord) -> str:
    """Build deterministic site key from parcel identity."""

    return f"site:{_short_hash(parcel.parcel_record_id)}"


def _resolution_id(
    site_input: SiteResolutionInput,
    candidates: list[SiteResolutionCandidate],
) -> str:
    """Build deterministic parcel-backed resolution id."""

    basis = "|".join(
        [
            site_input.evidence_id or "",
            site_input.source_name,
            ",".join(candidate.site_key for candidate in candidates),
        ]
    )
    return f"site-resolution:{_short_hash(basis)}"


def _short_hash(value: str) -> str:
    """Return a short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _unique(values: list[str]) -> list[str]:
    """Return values with duplicates removed in first-seen order."""

    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
