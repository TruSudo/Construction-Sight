"""Read-only exact-source opportunity review; never silently promote a source."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from sqlalchemy.orm import Session

from constructionsight.operator_dashboard import _project
from constructionsight.operator_dashboard_models import (
    RecordKind,
    SourceCandidatePreview,
    SourceCandidateReviewCheck,
)
from constructionsight.storage.domain_store import CeqaStore, PermitStore


class SourceRecordNotFound(LookupError):
    """The exact source-family/key pair does not exist."""


def build_source_candidate_preview(
    session: Session, *, kind: RecordKind, record_id: str
) -> SourceCandidatePreview:
    """Return a content-bound preview without writing, scoring, or reaching a network."""

    if kind not in {"ceqa", "permit"}:
        raise ValueError("a single source family is required")
    if (
        not record_id
        or len(record_id) > 255
        or record_id != record_id.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in record_id)
    ):
        raise ValueError("invalid exact source record identifier")
    record = (
        CeqaStore(session).get(record_id)
        if kind == "ceqa"
        else PermitStore(session).get(record_id)
    )
    if record is None:
        raise SourceRecordNotFound("source record not found")
    canonical = json.dumps(
        record.model_dump(mode="json", round_trip=True), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")
    source_digest = hashlib.sha256(canonical).hexdigest()
    identity = json.dumps(
        [kind, record_id], separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    candidate_key = "source-candidate:" + hashlib.sha256(identity).hexdigest()
    preview_digest = hashlib.sha256(
        (candidate_key + "|" + source_digest + "|v1").encode("utf-8")
    ).hexdigest()
    project = _project(record)
    site = record.site
    site_conflict = (
        site is not None and record.county is not None
        and site.county.strip().lower().removesuffix(" county")
        != record.county.strip().lower().removesuffix(" county")
    )
    county_state: Literal[
        "conflict", "missing", "out_of_scope", "source_claim_only"
    ] = (
        "conflict" if site_conflict else
        "missing" if project.coverage == "unknown" else
        "out_of_scope" if project.coverage == "outside_target_counties" else
        "source_claim_only"
    )
    evidence = bool(record.provenance)
    party_evidence = bool(record.entities) and all(
        bool(party.provenance) for party in record.entities
    )
    checks = [
        SourceCandidateReviewCheck(
            key="provenance", state="source_claim_only" if evidence else "missing",
            detail="Stored source provenance requires independent review."
            if evidence else "No source-record provenance; hold candidate review.",
        ),
        SourceCandidateReviewCheck(
            key="county", state=county_state,
            detail="Record and site county conflict." if site_conflict else
            "County scope is source-claimed and needs verification."
            if county_state == "source_claim_only" else
            "Target county eligibility is not established.",
        ),
        SourceCandidateReviewCheck(
            key="site", state="source_claim_only" if site and site.provenance else "missing",
            detail="Retained site requires independent parcel/location verification."
            if site and site.provenance else
            "A sourced site/parcel anchor has not been established.",
        ),
        SourceCandidateReviewCheck(
            key="parties", state="source_claim_only" if party_evidence else "missing",
            detail="Named parties require independent identity and role resolution."
            if party_evidence else "Named parties or their provenance are missing.",
        ),
        SourceCandidateReviewCheck(
            key="current_activity", state="review_required",
            detail="Historical dates/status cannot establish current construction activity.",
        ),
        SourceCandidateReviewCheck(
            key="deduplication", state="review_required",
            detail="No cross-source project identity or duplicate resolution occurred.",
        ),
        SourceCandidateReviewCheck(
            key="commercial_review", state="review_required",
            detail="Explicit operator review and separate lead authorization are required.",
        ),
    ]
    hold = not evidence or county_state in {"missing", "conflict", "out_of_scope"}
    return SourceCandidatePreview(
        candidate_key=candidate_key,
        preview_id="source-candidate-preview:" + preview_digest,
        normalized_source_sha256=source_digest,
        source_record=project,
        source_snapshot=record,
        state="hold" if hold else "review_required",
        checks=checks,
    )
