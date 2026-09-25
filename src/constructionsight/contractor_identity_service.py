"""Contractor identity resolution service."""

from __future__ import annotations

from constructionsight.contractor_identity_models import (
    ContractorIdentity,
    ContractorIdentityResolution,
    ContractorIdentityStatus,
    ContractorLicense,
    ContractorSourceKind,
    canonical_contractor_key,
    canonical_contractor_resolution_id,
    normalize_contractor_license_value,
    normalize_contractor_name_value,
)
from constructionsight.domain_types import confidence_band


def normalize_contractor_name(value: str) -> str:
    """Normalize contractor names for deterministic matching."""

    return normalize_contractor_name_value(value)


def normalize_contractor_license(value: str) -> str:
    """Normalize a contractor license into digits only."""

    return normalize_contractor_license_value(value)


def build_contractor_identity(
    *,
    display_name: str,
    source_kind: ContractorSourceKind = ContractorSourceKind.UNKNOWN,
    license_number: str | None = None,
    license_status: ContractorIdentityStatus = ContractorIdentityStatus.UNKNOWN,
    classification: str | None = None,
    contractor_group_key: str | None = None,
    county: str | None = None,
) -> ContractorIdentity:
    """Build a contractor identity from source signals."""

    normalized_name = normalize_contractor_name(display_name)
    license_signal = _license_signal(
        license_number=license_number,
        license_status=license_status,
        classification=classification,
        source_kind=source_kind,
    )
    score, reasons, limitations = _score_identity(
        normalized_name=normalized_name,
        license_signal=license_signal,
        contractor_group_key=contractor_group_key,
    )
    contractor_key = canonical_contractor_key(
        normalized_name=normalized_name,
        license_number=license_signal.license_number if license_signal else None,
        contractor_group_key=contractor_group_key,
    )
    status = (
        license_signal.status
        if license_signal is not None
        else ContractorIdentityStatus.UNKNOWN
    )
    return ContractorIdentity(
        contractor_key=contractor_key,
        display_name=display_name.strip(),
        normalized_name=normalized_name,
        source_kind=source_kind,
        license=license_signal,
        contractor_group_key=contractor_group_key,
        status=status,
        primary_trade=classification,
        county=county,
        confidence_score=score,
        confidence_band=confidence_band(score),
        reasons=reasons,
        limitations=limitations,
    )


def resolve_contractor_identity(
    identities: list[ContractorIdentity],
) -> ContractorIdentityResolution:
    """Resolve candidate contractor identities into a primary candidate when possible."""

    if not identities:
        return ContractorIdentityResolution(
            resolution_id=canonical_contractor_resolution_id([]),
            status="unresolved",
            candidates=[],
            limitations=["no contractor identity candidates provided"],
        )
    sorted_candidates = sorted(
        identities,
        key=lambda identity: (-identity.confidence_score, identity.contractor_key),
    )
    top_score = sorted_candidates[0].confidence_score
    top_candidates = [
        candidate
        for candidate in sorted_candidates
        if candidate.confidence_score == top_score
    ]
    status = "resolved" if len(top_candidates) == 1 else "ambiguous"
    primary_key = top_candidates[0].contractor_key if status == "resolved" else None
    limitations = [] if status == "resolved" else ["multiple contractor candidates tied"]
    return ContractorIdentityResolution(
        resolution_id=canonical_contractor_resolution_id(
            [candidate.contractor_key for candidate in sorted_candidates]
        ),
        status=status,
        candidates=sorted_candidates,
        primary_contractor_key=primary_key,
        limitations=limitations,
    )


def _license_signal(
    *,
    license_number: str | None,
    license_status: ContractorIdentityStatus,
    classification: str | None,
    source_kind: ContractorSourceKind,
) -> ContractorLicense | None:
    """Build a normalized license signal when license number exists."""

    if license_number is None:
        return None
    normalized_license = normalize_contractor_license(license_number)
    if not normalized_license:
        return None
    return ContractorLicense(
        license_number=normalized_license,
        status=license_status,
        classification=classification,
        source_kind=source_kind,
    )


def _score_identity(
    *,
    normalized_name: str,
    license_signal: ContractorLicense | None,
    contractor_group_key: str | None,
) -> tuple[int, list[str], list[str]]:
    """Score contractor identity quality."""

    score = 0
    reasons: list[str] = []
    limitations: list[str] = []
    if normalized_name:
        score += 35
        reasons.append("contractor name is present")
    else:
        limitations.append("contractor name is missing")
    if license_signal is not None:
        score += 45
        reasons.append("contractor license signal is present")
        if license_signal.status == ContractorIdentityStatus.ACTIVE:
            score += 10
            reasons.append("contractor license status is active")
        elif license_signal.status != ContractorIdentityStatus.UNKNOWN:
            limitations.append("contractor license status is not active")
    else:
        limitations.append("no contractor license signal was available")
    if contractor_group_key:
        score += 10
        reasons.append("contractor group signal is present")
    return min(score, 100), reasons, limitations
