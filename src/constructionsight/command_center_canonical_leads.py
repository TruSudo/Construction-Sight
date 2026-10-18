"""Phase 8: feed exact canonical evidence through existing lead-review rules.

A preview neither persists a lead nor authorizes outreach, pricing or bids.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

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
from constructionsight.lead_dedupe_models import LeadFingerprint
from constructionsight.lead_dedupe_service import (
    build_lead_fingerprint,
    check_lead_duplicate,
)
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.product_integration_models import ProductIntegrationReport
from constructionsight.product_integration_service import (
    build_product_integration,
    persist_product_integration,
)
from constructionsight.storage.database import (
    create_private_database_engine,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import (
    LeadFingerprintRecord,
    LeadWorkflowRecordRow,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine

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
    existing = existing_canonical_handoff(directory, investigation_id)
    return {
        "schema_version": "constructionsight.canonical-lead-review/v1",
        "existing_native_handoff": existing,
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


def existing_canonical_handoff(
    directory: Path, investigation_id: str,
) -> dict[str, Any] | None:
    """Read the original persisted workflow link; canonical identity never guesses by title."""
    engine = create_operator_read_engine(directory / "investigations.sqlite3")
    try:
        with Session(engine, autoflush=False) as session:
            fingerprints = session.scalars(
                select(LeadFingerprintRecord).where(
                    LeadFingerprintRecord.source_key == "canonical_investigation",
                    LeadFingerprintRecord.source_record_id == investigation_id,
                ).limit(2)
            ).all()
            if len(fingerprints) > 1:
                raise ValueError("conflicting canonical lead handoffs require review")
            if not fingerprints:
                return None
            workflow = session.scalars(
                select(LeadWorkflowRecordRow).where(
                    LeadWorkflowRecordRow.fingerprint_key
                    == fingerprints[0].fingerprint_key
                ).limit(2)
            ).all()
            if len(workflow) != 1:
                raise ValueError("canonical lead fingerprint/workflow lineage is incomplete")
            return {
                "workflow_id": workflow[0].workflow_id,
                "workflow_status": workflow[0].status,
                "fingerprint_key": fingerprints[0].fingerprint_key,
                "source_claim_only": True,
                "commercial_authority_granted": False,
            }
    finally:
        engine.dispose()


def retain_reviewed_canonical_candidate(
    directory: Path, payload: dict[str, Any],
) -> dict[str, Any]:
    """Persist the original governed lead stages atomically after explicit review.

    A SQLite IMMEDIATE transaction serializes checks against concurrent original
    worker updates and other operators. Neither source history nor commercial
    authority is mutated.
    """
    if set(payload) != {
        "investigation_id", "expected_evidence_id", "expected_evidence_sha256",
        "expected_event_anchor", "reason", "caller_confirmation",
    }:
        raise ValueError("exact canonical lead review fields required")
    identity = payload["investigation_id"]
    reason = payload["reason"]
    if (
        not isinstance(identity, str) or not 1 <= len(identity) <= 255
        or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
        or not isinstance(payload["expected_evidence_id"], str)
        or not isinstance(payload["expected_evidence_sha256"], str)
        or not isinstance(payload["expected_event_anchor"], str)
    ):
        raise ValueError("explicit review, exact identity and evidence receipt required")
    engine = create_private_database_engine(
        directory / "investigations.sqlite3", create=False,
    )
    try:
        with managed_session(session_factory(engine)) as session:
            # The worker and every duplicate reviewer share this single private
            # DB, so lock it before inspecting the current retained evidence.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            reviewed = canonical_lead_preview(directory, identity)
            if (
                reviewed["current_evidence_id"] != payload["expected_evidence_id"]
                or reviewed["current_evidence_sha256"]
                != payload["expected_evidence_sha256"]
                or reviewed["event_anchor"] != payload["expected_event_anchor"]
            ):
                raise ValueError("evidence changed; repeat canonical lead review")
            if reviewed["existing_native_handoff"] is not None:
                raise ValueError("canonical investigation already has a retained lead handoff")
            rows = session.scalars(select(LeadFingerprintRecord).limit(5001)).all()
            if len(rows) > 5000:
                raise ValueError("persisted duplicate scan exceeds review bound")
            existing = [
                LeadFingerprint.model_validate(json.loads(row.payload_json))
                for row in rows
            ]
            product = ProductIntegrationReport.model_validate(
                reviewed["original_product_integration"]
            )
            # A stable canonical identity survives a source/title revision.
            # Same-site evidence still invokes the original REVIEW_NEEDED dedupe.
            fingerprint = build_lead_fingerprint(
                package=product.review_package,
                site_key=product.site_resolution.primary_site_key,
                source_key="canonical_investigation",
                source_record_id=identity,
            )
            duplicate = check_lead_duplicate(fingerprint, existing)
            workflow = create_lead_workflow(
                package=product.review_package, duplicate_result=duplicate,
            ).model_copy(update={"notes": [
                "Canonical investigation: " + identity,
                "Operator retained candidate for human review: " + reason.strip(),
                "Original source evidence: " + reviewed["current_evidence_id"],
            ]})
            if workflow.status.value not in {"hold", "monitor", "review"}:
                raise ValueError("unverified claims cannot be promoted to actionable lead")
            retained = ProductIntegrationReport.model_validate(
                product.model_copy(update={
                    "fingerprint": fingerprint,
                    "duplicate_result": duplicate,
                    "workflow": workflow,
                }).model_dump(mode="json")
            )
            persist_product_integration(session, retained)
            result: dict[str, Any] = {
                "schema_version": "constructionsight.canonical-lead-retention/v1",
                "canonical_investigation_id": identity,
                "source_entity_id": reviewed["source_entity_id"],
                "source_evidence_id": reviewed["current_evidence_id"],
                "workflow_id": retained.workflow.workflow_id,
                "workflow_status": retained.workflow.status.value,
                "duplicate_status": duplicate.status.value,
                "lead_review_status": retained.review_package.status.value,
                "persisted": True,
                "human_review_required": True,
                "outreach_authorized": False,
                "bid_authorized": False,
                "commercial_authority_granted": False,
                "source_claim_only": True,
            }
        return result
    except SQLAlchemyError as exc:
        raise ValueError("canonical review workflow could not be committed") from exc
    finally:
        engine.dispose()
