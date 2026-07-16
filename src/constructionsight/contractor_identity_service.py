"""Contractor identity resolution service."""

from __future__ import annotations

import hashlib
import re

from constructionsight.contractor_identity_models import (
    ContractorIdentity,
    ContractorIdentityResolution,
    ContractorIdentityStatus,
    ContractorLicense,
    ContractorSourceKind,
)
from constructionsight.domain_types import confidence_band

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^A-Z0-9]+")
_LICENSE_RE = re.compile(r"\d+")


def normalize_contractor_name(value: str) -> str:
    """Normalize contractor names for deterministic matching."""

    cleaned = _NON_WORD_RE.sub(" ", value.upper())
    return _SPACE_RE.sub(" ", cleaned).strip()


def normalize_contractor_license(value: str) -> str:
    """Normalize a contractor license into digits only."""

    return "".join(_LICENSE_RE.findall(value))


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
    contractor_key = _contractor_key(
        normalized_name=normalized_name,
        license_signal=license_signal,
        contractor_group_key=contractor_group_key,
    )
    status = (
        license_signal.status if license_signal is not None else ContractorIdentityStatus.UNKNOWN
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
            resolution_id="contractor-resolution:empty",
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
        candidate for candidate in sorted_candidates if candidate.confidence_score == top_score
    ]
    status = "resolved" if len(top_candidates) == 1 else "ambiguous"
    primary_key = top_candidates[0].contractor_key if status == "resolved" else None
    limitations = [] if status == "resolved" else ["multiple contractor candidates tied"]
    return ContractorIdentityResolution(
        resolution_id=_resolution_id(sorted_candidates),
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


def _contractor_key(
    *,
    normalized_name: str,
    license_signal: ContractorLicense | None,
    contractor_group_key: str | None,
) -> str:
    """Build deterministic contractor key."""

    basis = "|".join(
        [
            normalized_name,
            license_signal.license_number if license_signal else "",
            contractor_group_key or "",
        ]
    )
    return f"contractor:{_short_hash(basis)}"


def _resolution_id(candidates: list[ContractorIdentity]) -> str:
    """Build deterministic contractor resolution id."""

    basis = ",".join(candidate.contractor_key for candidate in candidates)
    return f"contractor-resolution:{_short_hash(basis)}"


def _short_hash(value: str) -> str:
    """Return a short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
