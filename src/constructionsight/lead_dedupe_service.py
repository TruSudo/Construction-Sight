"""Lead duplicate suppression service."""

from __future__ import annotations

import hashlib
import json
import re

from constructionsight.lead_dedupe_models import (
    LeadDuplicateResult,
    LeadDuplicateStatus,
    LeadFingerprint,
)
from constructionsight.lead_review_models import LeadReviewPackage

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^A-Z0-9]+")


def normalize_lead_title(value: str) -> str:
    """Normalize lead title text for duplicate checks."""

    cleaned = _NON_WORD_RE.sub(" ", value.upper())
    return _SPACE_RE.sub(" ", cleaned).strip()


def build_lead_fingerprint(
    *,
    package: LeadReviewPackage,
    site_key: str | None = None,
    source_key: str | None = None,
    source_record_id: str | None = None,
    title: str | None = None,
) -> LeadFingerprint:
    """Build deterministic lead fingerprint from review package and source hints."""

    normalized_title = normalize_lead_title(title) if title else None
    fingerprint_key = _fingerprint_key(
        site_key=site_key,
        source_key=source_key,
        source_record_id=source_record_id,
        normalized_title=normalized_title,
    )
    return LeadFingerprint(
        fingerprint_key=fingerprint_key,
        base_candidate_id=package.base_candidate_id,
        site_key=site_key,
        source_key=source_key,
        source_record_id=source_record_id,
        normalized_title=normalized_title,
        lead_score=package.lead_score,
    )


def check_lead_duplicate(
    candidate: LeadFingerprint,
    existing: list[LeadFingerprint],
) -> LeadDuplicateResult:
    """Compare one candidate fingerprint against existing lead fingerprints."""

    duplicate_matches: list[str] = []
    review_matches: list[str] = []
    reasons: list[str] = []
    for fingerprint in existing:
        if candidate.fingerprint_key == fingerprint.fingerprint_key:
            duplicate_matches.append(fingerprint.fingerprint_key)
            reasons.append("exact lead fingerprint already exists")
            continue
        if _same_site(candidate, fingerprint):
            review_matches.append(fingerprint.fingerprint_key)
            reasons.append("same site key appears in existing lead")
        elif _same_source_record(candidate, fingerprint):
            review_matches.append(fingerprint.fingerprint_key)
            reasons.append("same source record appears in existing lead")
    if duplicate_matches:
        status = LeadDuplicateStatus.DUPLICATE
        matched_keys = duplicate_matches
    elif review_matches:
        status = LeadDuplicateStatus.REVIEW_NEEDED
        matched_keys = review_matches
    else:
        status = LeadDuplicateStatus.UNIQUE
        matched_keys = []
        reasons.append("no duplicate lead fingerprint found")
    return LeadDuplicateResult(
        result_id=_result_id(candidate, status, matched_keys, reasons),
        status=status,
        candidate=candidate,
        matched_fingerprint_keys=_unique(matched_keys),
        reasons=_unique(reasons),
    )


def _same_site(candidate: LeadFingerprint, existing: LeadFingerprint) -> bool:
    """Return whether both fingerprints share a site key."""

    return candidate.site_key is not None and candidate.site_key == existing.site_key


def _same_source_record(candidate: LeadFingerprint, existing: LeadFingerprint) -> bool:
    """Return whether both fingerprints share a source record."""

    return (
        candidate.source_key is not None
        and candidate.source_record_id is not None
        and candidate.source_key == existing.source_key
        and candidate.source_record_id == existing.source_record_id
    )


def _fingerprint_key(
    *,
    site_key: str | None,
    source_key: str | None,
    source_record_id: str | None,
    normalized_title: str | None,
) -> str:
    """Build deterministic lead fingerprint key."""

    basis = "|".join(
        [site_key or "", source_key or "", source_record_id or "", normalized_title or ""]
    )
    return f"lead-fingerprint:{_short_hash(basis)}"


def _result_id(
    candidate: LeadFingerprint,
    status: LeadDuplicateStatus,
    matched_keys: list[str],
    reasons: list[str],
) -> str:
    """Bind each candidate's immutable verdict to a versioned semantic identity.

    Observation time and score may change on a rescan; candidate attribution,
    match basis and decision content may not share an old verdict identity.
    Existing persisted v1 IDs remain readable without rewriting their receipts.
    """

    basis = json.dumps(
        {
            "schema_version": "constructionsight.lead-duplicate/v2",
            "candidate": candidate.model_dump(mode="json", exclude={"created_at", "lead_score"}),
            "status": status.value,
            "matched_fingerprint_keys": sorted(set(matched_keys)),
            "reasons": sorted(set(reasons)),
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return f"lead-duplicate:v2:{hashlib.sha256(basis.encode('utf-8')).hexdigest()}"


def _short_hash(value: str) -> str:
    """Return short deterministic hash."""

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
