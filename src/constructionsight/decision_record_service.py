"""Decision record builder and site-match helpers."""

from __future__ import annotations

import hashlib
import re

from constructionsight.decision_record_models import (
    DecisionKind,
    DecisionMatchStatus,
    DecisionRecord,
    DecisionSiteMatch,
    DecisionSourceKind,
)
from constructionsight.domain_types import confidence_band
from constructionsight.site_resolution_service import normalize_apn

_SPACE_RE = re.compile(r"\s+")
_NON_WORD_RE = re.compile(r"[^A-Z0-9]+")


def normalize_decision_title(value: str) -> str:
    """Normalize decision titles for deterministic matching."""

    cleaned = _NON_WORD_RE.sub(" ", value.upper())
    return _SPACE_RE.sub(" ", cleaned).strip()


def build_decision_record(
    *,
    source_key: str,
    title: str,
    source_record_id: str | None = None,
    source_kind: DecisionSourceKind = DecisionSourceKind.UNKNOWN,
    decision_kind: DecisionKind = DecisionKind.UNKNOWN,
    jurisdiction: str | None = None,
    county: str | None = None,
    case_number: str | None = None,
    project_name: str | None = None,
    site_key: str | None = None,
    apn: str | None = None,
    applicant_name: str | None = None,
    developer_name: str | None = None,
    source_url: str | None = None,
    summary: str | None = None,
) -> DecisionRecord:
    """Build a decision record from source-neutral decision signals."""

    normalized_title = normalize_decision_title(title)
    normalized_apn = normalize_apn(apn) if apn else None
    score, reasons, limitations = _score_decision(
        normalized_title=normalized_title,
        source_kind=source_kind,
        decision_kind=decision_kind,
        site_key=site_key,
        apn=normalized_apn,
        source_url=source_url,
        applicant_name=applicant_name,
        developer_name=developer_name,
    )
    decision_key = _decision_key(
        source_key=source_key,
        source_record_id=source_record_id,
        normalized_title=normalized_title,
        case_number=case_number,
    )
    return DecisionRecord(
        decision_key=decision_key,
        source_key=source_key,
        source_record_id=source_record_id,
        source_kind=source_kind,
        decision_kind=decision_kind,
        title=title.strip(),
        normalized_title=normalized_title,
        jurisdiction=jurisdiction,
        county=county,
        case_number=case_number,
        project_name=project_name,
        site_key=site_key,
        apn=normalized_apn,
        applicant_name=applicant_name,
        developer_name=developer_name,
        source_url=source_url,
        summary=summary,
        confidence_score=score,
        confidence_band=confidence_band(score),
        reasons=reasons,
        limitations=limitations,
    )


def match_decision_to_site(decision: DecisionRecord) -> DecisionSiteMatch:
    """Build a first-pass decision-to-site match from embedded site/APN hints."""

    score = 0
    reasons: list[str] = []
    limitations: list[str] = []
    if decision.site_key:
        score += 70
        reasons.append("decision includes a site key")
    if decision.apn:
        score += 20
        reasons.append("decision includes an APN hint")
    if not decision.site_key and not decision.apn:
        limitations.append("decision has no site key or APN hint")
    status = _match_status(score, decision.site_key)
    return DecisionSiteMatch(
        decision_key=decision.decision_key,
        site_key=decision.site_key,
        apn=decision.apn,
        status=status,
        confidence_score=score,
        confidence_band=confidence_band(score),
        reasons=reasons,
        limitations=limitations,
    )


def _score_decision(
    *,
    normalized_title: str,
    source_kind: DecisionSourceKind,
    decision_kind: DecisionKind,
    site_key: str | None,
    apn: str | None,
    source_url: str | None,
    applicant_name: str | None,
    developer_name: str | None,
) -> tuple[int, list[str], list[str]]:
    """Score decision record quality."""

    score = 0
    reasons: list[str] = []
    limitations: list[str] = []
    if normalized_title:
        score += 20
        reasons.append("decision title is present")
    if source_kind != DecisionSourceKind.UNKNOWN:
        score += 15
        reasons.append("decision source kind is known")
    else:
        limitations.append("decision source kind is unknown")
    if decision_kind != DecisionKind.UNKNOWN:
        score += 15
        reasons.append("decision kind is classified")
    else:
        limitations.append("decision kind is unknown")
    if site_key:
        score += 25
        reasons.append("decision includes a site key")
    elif apn:
        score += 15
        reasons.append("decision includes an APN hint")
    else:
        limitations.append("decision has no site or APN hint")
    if source_url:
        score += 15
        reasons.append("decision includes source URL")
    else:
        limitations.append("decision source URL is missing")
    if applicant_name or developer_name:
        score += 10
        reasons.append("decision includes applicant or developer signal")
    return min(score, 100), reasons, limitations


def _match_status(score: int, site_key: str | None) -> DecisionMatchStatus:
    """Return decision-site match status."""

    if score >= 70 and site_key is not None:
        return DecisionMatchStatus.MATCHED
    if score > 0:
        return DecisionMatchStatus.REVIEW_NEEDED
    return DecisionMatchStatus.UNMATCHED


def _decision_key(
    *,
    source_key: str,
    source_record_id: str | None,
    normalized_title: str,
    case_number: str | None,
) -> str:
    """Build deterministic decision key."""

    basis = "|".join([source_key, source_record_id or "", normalized_title, case_number or ""])
    return f"decision:{_short_hash(basis)}"


def _short_hash(value: str) -> str:
    """Return a short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
