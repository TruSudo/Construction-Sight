"""Source-neutral parcel and site-resolution service."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Iterable

from constructionsight.domain_types import confidence_band
from constructionsight.intake_models import (
    ExtractedMaterialFact,
    MaterialFactKind,
    UniversalIntakeRecord,
)
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

_APN_DIGIT_RE = re.compile(r"\d+")
_SPACE_RE = re.compile(r"\s+")
_COORDINATE_RE = re.compile(r"(?P<lat>-?\d{1,2}(?:\.\d+)?)\s*,\s*(?P<lon>-?\d{1,3}(?:\.\d+)?)")


def resolve_site_from_intake(intake: UniversalIntakeRecord) -> SiteResolutionResult:
    """Resolve a site candidate from a universal intake record."""

    return resolve_site(build_site_resolution_input_from_intake(intake))


def build_site_resolution_input_from_intake(intake: UniversalIntakeRecord) -> SiteResolutionInput:
    """Build a site-resolution input from extracted intake facts."""

    identifiers: list[SiteIdentifier] = []
    geometry_hints: list[GeometryHint] = []
    for fact in intake.extracted_facts:
        identifier = _identifier_from_fact(fact)
        if identifier is not None:
            identifiers.append(identifier)
        geometry_hint = _geometry_hint_from_fact(fact, intake.evidence.source_name)
        if geometry_hint is not None:
            geometry_hints.append(geometry_hint)

    source_hints = dict(intake.source_hints)
    if intake.evidence.source_family:
        source_hints.setdefault("source_family", intake.evidence.source_family)
    if intake.evidence.source_url:
        source_hints.setdefault("source_url", intake.evidence.source_url)

    return SiteResolutionInput(
        source_name=intake.evidence.source_name,
        evidence_id=intake.evidence.evidence_id,
        identifiers=_dedupe_identifiers(identifiers),
        geometry_hints=geometry_hints,
        source_hints=source_hints,
    )


def resolve_site(site_input: SiteResolutionInput) -> SiteResolutionResult:
    """Resolve a source-neutral site candidate from identifiers and geometry hints."""

    identifiers = site_input.identifiers
    if not identifiers and not site_input.geometry_hints:
        return _unresolved(
            site_input,
            ["no APN, address, coordinate, or geometry signal present"],
        )

    conflicts = _detect_conflicts(identifiers)
    candidate = _build_candidate(site_input, conflicts)
    status = _status_for_candidate(candidate, conflicts)
    return SiteResolutionResult(
        resolution_id=_resolution_id(site_input, candidate.site_key),
        source_name=site_input.source_name,
        evidence_id=site_input.evidence_id,
        status=status,
        primary_site_key=candidate.site_key,
        candidates=[candidate],
        conflicts=conflicts,
        limitations=_result_limitations(candidate, conflicts),
    )


def normalize_apn(value: str) -> str:
    """Normalize an assessor parcel number into digits only."""

    return "".join(_APN_DIGIT_RE.findall(value))


def normalize_address(value: str) -> str:
    """Normalize an address-like string for deterministic matching."""

    return _SPACE_RE.sub(" ", value.strip().upper())


def normalize_jurisdiction(value: str) -> str:
    """Normalize a jurisdiction or county hint."""

    return _SPACE_RE.sub(" ", value.strip().title())


def _identifier_from_fact(fact: ExtractedMaterialFact) -> SiteIdentifier | None:
    """Convert a material fact into a site identifier when possible."""

    value = fact.normalized_value or fact.value
    if fact.fact_kind == MaterialFactKind.APN:
        normalized = normalize_apn(value)
        if not normalized:
            return None
        return _identifier(SiteIdentifierKind.APN, fact, normalized, 90)
    if fact.fact_kind == MaterialFactKind.ADDRESS:
        return _identifier(SiteIdentifierKind.ADDRESS, fact, normalize_address(value), 75)
    if fact.fact_kind == MaterialFactKind.AGENCY:
        return _identifier(
            SiteIdentifierKind.JURISDICTION,
            fact,
            normalize_jurisdiction(value),
            35,
        )
    return None


def _geometry_hint_from_fact(
    fact: ExtractedMaterialFact,
    source_name: str,
) -> GeometryHint | None:
    """Extract coordinate geometry hints from generic material facts."""

    value = fact.normalized_value or fact.value
    match = _COORDINATE_RE.search(value)
    if match is None:
        return None
    latitude = float(match.group("lat"))
    longitude = float(match.group("lon"))
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return GeometryHint(
        geometry_kind=GeometryHintKind.POINT,
        latitude=latitude,
        longitude=longitude,
        source_name=source_name,
        evidence_id=fact.evidence_id,
        confidence_score=80,
    )


def _identifier(
    identifier_kind: SiteIdentifierKind,
    fact: ExtractedMaterialFact,
    normalized_value: str,
    confidence_score: int,
) -> SiteIdentifier:
    """Build a site identifier from an extracted fact."""

    return SiteIdentifier(
        identifier_kind=identifier_kind,
        value=fact.value,
        normalized_value=normalized_value,
        evidence_id=fact.evidence_id,
        fact_id=fact.fact_id,
        source_field=fact.source_field,
        confidence_score=confidence_score,
    )


def _dedupe_identifiers(identifiers: list[SiteIdentifier]) -> list[SiteIdentifier]:
    """Dedupe identifiers while preserving first-seen order."""

    seen: set[tuple[SiteIdentifierKind, str]] = set()
    deduped: list[SiteIdentifier] = []
    for identifier in identifiers:
        key = (identifier.identifier_kind, identifier.normalized_value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(identifier)
    return deduped


def _detect_conflicts(identifiers: Iterable[SiteIdentifier]) -> list[str]:
    """Detect multiple values for the same hard site identifier kind."""

    hard_identifier_kinds = {SiteIdentifierKind.APN, SiteIdentifierKind.ADDRESS}
    by_kind: dict[SiteIdentifierKind, set[str]] = defaultdict(set)
    for identifier in identifiers:
        if identifier.identifier_kind in hard_identifier_kinds:
            by_kind[identifier.identifier_kind].add(identifier.normalized_value)

    conflicts: list[str] = []
    for identifier_kind in (SiteIdentifierKind.APN, SiteIdentifierKind.ADDRESS):
        values = sorted(by_kind.get(identifier_kind, set()))
        if len(values) > 1:
            conflicts.append(f"multiple {identifier_kind.value} values found: {', '.join(values)}")
    return conflicts


def _build_candidate(
    site_input: SiteResolutionInput,
    conflicts: list[str],
) -> SiteResolutionCandidate:
    """Build a deterministic primary candidate from the strongest site signals."""

    identifiers = site_input.identifiers
    apn = _first_identifier_value(identifiers, SiteIdentifierKind.APN)
    address = _first_identifier_value(identifiers, SiteIdentifierKind.ADDRESS)
    jurisdiction = _first_identifier_value(identifiers, SiteIdentifierKind.JURISDICTION)
    county = _county_hint(site_input)
    point = _first_point(site_input.geometry_hints)
    score = _score_candidate(identifiers, site_input.geometry_hints, conflicts)
    site_key = _site_key(
        apn=apn,
        address=address,
        latitude=point.latitude if point else None,
        longitude=point.longitude if point else None,
        county=county,
        jurisdiction=jurisdiction,
    )

    return SiteResolutionCandidate(
        site_key=site_key,
        match_strength=_match_strength(score, conflicts),
        confidence_score=score,
        confidence_band=confidence_band(score),
        county=county,
        jurisdiction=jurisdiction,
        apn=apn,
        address=address,
        latitude=point.latitude if point else None,
        longitude=point.longitude if point else None,
        supporting_identifiers=identifiers,
        geometry_hints=site_input.geometry_hints,
        reasons=_candidate_reasons(identifiers, site_input.geometry_hints),
        limitations=_candidate_limitations(
            identifiers,
            site_input.geometry_hints,
            conflicts,
        ),
    )


def _score_candidate(
    identifiers: list[SiteIdentifier],
    geometry_hints: list[GeometryHint],
    conflicts: list[str],
) -> int:
    """Score candidate quality based on anchor strength and conflicts."""

    score = 0
    if _has_identifier(identifiers, SiteIdentifierKind.APN):
        score += 45
    if _has_identifier(identifiers, SiteIdentifierKind.ADDRESS):
        score += 30
    if geometry_hints:
        score += 20
    if _has_identifier(identifiers, SiteIdentifierKind.JURISDICTION):
        score += 5
    if conflicts:
        score -= 30
    return max(0, min(100, score))


def _status_for_candidate(
    candidate: SiteResolutionCandidate,
    conflicts: list[str],
) -> SiteResolutionStatus:
    """Return resolution status for a candidate."""

    if conflicts:
        return SiteResolutionStatus.CONFLICTING
    if candidate.confidence_score >= 75:
        return SiteResolutionStatus.RESOLVED
    if candidate.confidence_score > 0:
        return SiteResolutionStatus.PARTIAL
    return SiteResolutionStatus.UNRESOLVED


def _match_strength(score: int, conflicts: list[str]) -> SiteMatchStrength:
    """Return match strength from score and conflict state."""

    if conflicts:
        return SiteMatchStrength.WEAK
    if score >= 95:
        return SiteMatchStrength.EXACT
    if score >= 75:
        return SiteMatchStrength.STRONG
    if score >= 50:
        return SiteMatchStrength.MODERATE
    if score > 0:
        return SiteMatchStrength.WEAK
    return SiteMatchStrength.NONE


def _candidate_reasons(
    identifiers: list[SiteIdentifier],
    geometry_hints: list[GeometryHint],
) -> list[str]:
    """Return deterministic reasons explaining the candidate."""

    reasons: list[str] = []
    if _has_identifier(identifiers, SiteIdentifierKind.APN):
        reasons.append("APN provides a strong parcel identity anchor")
    if _has_identifier(identifiers, SiteIdentifierKind.ADDRESS):
        reasons.append("address provides a mappable site anchor")
    if geometry_hints:
        reasons.append("coordinate or geometry hint provides a spatial anchor")
    if _has_identifier(identifiers, SiteIdentifierKind.JURISDICTION):
        reasons.append("jurisdiction hint helps scope the source family")
    return reasons


def _candidate_limitations(
    identifiers: list[SiteIdentifier],
    geometry_hints: list[GeometryHint],
    conflicts: list[str],
) -> list[str]:
    """Return limitations for the candidate."""

    limitations: list[str] = []
    if not _has_identifier(identifiers, SiteIdentifierKind.APN):
        limitations.append("no APN was available for parcel-exact matching")
    if not _has_identifier(identifiers, SiteIdentifierKind.ADDRESS):
        limitations.append("no address was available for address-to-parcel matching")
    if not geometry_hints:
        limitations.append("no coordinate or geometry hint was available")
    limitations.extend(conflicts)
    return _unique(limitations)


def _result_limitations(
    candidate: SiteResolutionCandidate,
    conflicts: list[str],
) -> list[str]:
    """Return result-level limitations."""

    limitations = list(candidate.limitations)
    if conflicts:
        limitations.append("conflicts must be resolved before treating this as one parcel")
    return _unique(limitations)


def _unresolved(
    site_input: SiteResolutionInput,
    limitations: list[str],
) -> SiteResolutionResult:
    """Return an unresolved site-resolution result."""

    basis = site_input.evidence_id or site_input.source_name
    return SiteResolutionResult(
        resolution_id=f"site-resolution:{_short_hash(basis)}",
        source_name=site_input.source_name,
        evidence_id=site_input.evidence_id,
        status=SiteResolutionStatus.UNRESOLVED,
        candidates=[],
        limitations=limitations,
    )


def _site_key(
    *,
    apn: str | None,
    address: str | None,
    latitude: float | None,
    longitude: float | None,
    county: str | None,
    jurisdiction: str | None,
) -> str:
    """Build a deterministic site key from strongest available anchor values."""

    parts = ["CA", county or "", jurisdiction or "", apn or "", address or ""]
    if latitude is not None and longitude is not None:
        parts.extend([f"{latitude:.6f}", f"{longitude:.6f}"])
    basis = "|".join(parts)
    return f"site:{_short_hash(basis)}"


def _resolution_id(site_input: SiteResolutionInput, site_key: str) -> str:
    """Build a deterministic resolution id."""

    basis = "|".join([site_input.evidence_id or "", site_input.source_name, site_key])
    return f"site-resolution:{_short_hash(basis)}"


def _short_hash(value: str) -> str:
    """Return a short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _first_identifier_value(
    identifiers: list[SiteIdentifier],
    identifier_kind: SiteIdentifierKind,
) -> str | None:
    """Return first normalized value for an identifier kind."""

    for identifier in identifiers:
        if identifier.identifier_kind == identifier_kind:
            return identifier.normalized_value
    return None


def _has_identifier(
    identifiers: list[SiteIdentifier],
    identifier_kind: SiteIdentifierKind,
) -> bool:
    """Return whether identifiers include a kind."""

    return any(identifier.identifier_kind == identifier_kind for identifier in identifiers)


def _first_point(geometry_hints: list[GeometryHint]) -> GeometryHint | None:
    """Return first point-like geometry hint."""

    point_kinds = {GeometryHintKind.POINT, GeometryHintKind.CENTROID}
    for geometry_hint in geometry_hints:
        if geometry_hint.geometry_kind in point_kinds:
            return geometry_hint
    return None


def _county_hint(site_input: SiteResolutionInput) -> str | None:
    """Return normalized county hint when available."""

    for key in ("county", "county_name"):
        value = site_input.source_hints.get(key)
        if value:
            return normalize_jurisdiction(value).removesuffix(" County")
    return None


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
