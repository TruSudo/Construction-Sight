"""Phase 8: feed exact canonical evidence through existing lead-review rules.

A preview neither persists a lead nor authorizes outreach, pricing or bids.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from constructionsight.command_center_investigations import investigation_view
from constructionsight.intake_models import (
    DigitalFormatFamily,
    ExtractedMaterialFact,
    FactConfidence,
    FormatDetection,
    IntakeEvidenceRef,
    IntakeRouting,
    IntakeUnderstandingStatus,
    MaterialFactKind,
    UniversalIntakeRecord,
)
from constructionsight.product_integration_service import build_product_integration

_ARTIFACT_FACTS = {
    "apn": MaterialFactKind.APN,
    "exact_site_address": MaterialFactKind.ADDRESS,
    "ceqa_sch_number": MaterialFactKind.SCH_NUMBER,
    "permit_number": MaterialFactKind.PERMIT_NUMBER,
}


def canonical_lead_preview(directory: Path, investigation_id: str) -> dict[str, Any]:
    """Review one current source anchor, never guessed cross-source project facts."""
    if not isinstance(investigation_id, str) or not 1 <= len(investigation_id) <= 255:
        raise ValueError("one exact canonical investigation required")
    dossier = investigation_view(directory, investigation_id=investigation_id)
    if dossier["investigation"]["project_cluster_id"] != investigation_id:
        raise ValueError("investigation identity changed; reopen the current dossier")
    if dossier["pending_association_reviews"] or any(dossier.get(key) for key in (
        "sources_truncated", "evidence_truncated", "relationships_truncated",
        "parties_truncated", "candidate_links_truncated",
    )):
        raise ValueError("investigation has unresolved or truncated source context")
    anchors = [
        m for m in dossier["source_membership"] if m["membership_basis"] == "source_anchor"
    ]
    if len(anchors) != 1:
        raise ValueError("source anchor absent or ambiguous; source review required")
    anchor = anchors[0]
    current = [
        value for value in dossier["source_observations"]
        if value["evidence"]["evidence_id"] == anchor["current_evidence_id"]
        and value["evidence"]["source_record_id"] == anchor["source_record_id"]
        and value["evidence"]["source_family"] == anchor["source_family"]
    ]
    if len(current) != 1:
        raise ValueError("current source evidence no longer matches the canonical anchor")
    record = current[0]
    evidence = record["evidence"]
    digest = evidence.get("content_hash")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("original evidence has no exact retained integrity digest")
    artifacts = record.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("source artifacts require review")
    facts: list[ExtractedMaterialFact] = []
    title = record.get("title")
    if isinstance(title, str) and title.strip():
        facts.append(ExtractedMaterialFact(
            fact_id="source-title:" + digest,
            fact_kind=MaterialFactKind.PROJECT_TITLE,
            value=title, evidence_id=evidence["evidence_id"],
            confidence=FactConfidence.SOURCE_CLAIMED, source_field="title",
        ))
    for key, kind in _ARTIFACT_FACTS.items():
        values = artifacts.get(key, [])
        if not isinstance(values, list) or len(values) > 1 or any(
            not isinstance(v, str) or not v.strip() for v in values
        ):
            raise ValueError("ambiguous source artifacts must be reviewed")
        for value in values:
            facts.append(ExtractedMaterialFact(
                fact_id=f"source-{key}:" + digest, fact_kind=kind,
                value=value, evidence_id=evidence["evidence_id"],
                confidence=FactConfidence.SOURCE_CLAIMED, source_field=key,
                context="source claim; not independently confirmed",
            ))
    if not facts:
        raise ValueError("no current source facts for original lead assessment")
    normalized = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    hints = {
        kind.value: artifacts[key][0]
        for key, kind in (
            ("ceqa_sch_number", MaterialFactKind.SCH_NUMBER),
            ("permit_number", MaterialFactKind.PERMIT_NUMBER),
        ) if artifacts.get(key)
    }
    intake = UniversalIntakeRecord(
        intake_id="canonical-intake:" + digest,
        evidence=IntakeEvidenceRef(
            evidence_id=evidence["evidence_id"],
            source_name=evidence["source_name"],
            source_family=evidence["source_family"],
            source_url=evidence.get("source_url"),
            observed_at=evidence["observed_at"] or evidence["retrieved_at"],
            byte_count=len(normalized), sha256=digest,
            access_method="retained_normalized_projection",
            lawful_basis="already_retained_public_source_evidence",
            limitations=[
                "Projection byte count is not original source byte length.",
                "Source content integrity does not verify site identity or contact authority.",
            ],
        ),
        format_detection=FormatDetection(format_family=DigitalFormatFamily.JSON),
        understanding_status=IntakeUnderstandingStatus.STRUCTURED,
        routing=IntakeRouting.HUMAN_REVIEW,
        extracted_facts=facts, record_hints=hints,
        source_hints={
            "canonical_investigation_id": investigation_id,
            "source_entity_id": anchor["source_id"],
            "source_record_id": anchor["source_record_id"],
        },
        next_action="Independent operator review required before any commerce.",
    )
    report = build_product_integration(intake)
    if report.workflow.status.value not in {"hold", "monitor", "review"}:
        raise ValueError("source claims cannot enter an actionable workflow")
    return {
        "schema_version": "constructionsight.canonical-lead-review/v1",
        "canonical_investigation_id": investigation_id,
        "source_entity_id": anchor["source_id"],
        "current_evidence_id": evidence["evidence_id"],
        "current_evidence_sha256": digest,
        "source_record_id": anchor["source_record_id"],
        "event_anchor": dossier["event_anchor"],
        "original_product_integration": report.model_dump(mode="json"),
        "lead_review_status": report.review_package.status.value,
        "provisional_workflow_status": report.workflow.status.value,
        "persisted": False,
        "dedupe_against_persisted_leads_complete": False,
        "commercial_authority_granted": False,
        "outreach_authorized": False,
        "bid_authorized": False,
        "limitations": [
            "Read-only original pipeline assessment, not a qualified commercial lead.",
            "Persisted lead duplicates and authority remain subject to operator review.",
        ],
    }
